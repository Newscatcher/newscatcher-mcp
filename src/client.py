"""Thin HTTP client for the NewsCatcher News API and Agent API.

Auth header, timeouts, polite retries (429 with Retry-After, 502/503/504), a pacing gate for ``/articles`` (the free
plan allows one request a second) and API errors turned into short messages an agent can act on.

Agent API writes (start a run, create a monitor or a list) are never retried after a 5xx or a dropped connection:
those endpoints take no idempotency key, so a retry could start a second paid run.
"""

from __future__ import annotations

import asyncio
import json
import random
import time
from typing import Any, Literal

import httpx

from src import VERSION
from src.config import Config
from src.log import setup_logging

logger = setup_logging(__name__)

Api = Literal["news", "agent"]

RETRYABLE = {429, 502, 503, 504}
MAY_HAVE_GONE_THROUGH = (
    " The request may have gone through: check (get_research with no run_id lists runs; get_monitor lists monitors)"
    " before trying again."
)

# Patched in tests so retry back-off does not slow the suite down.
_sleep = asyncio.sleep


class ApiError(Exception):
    """A NewsCatcher API error, with what is needed to tell the agent what to do next."""

    def __init__(
        self,
        status: int,
        message: str,
        code: str | None = None,
        correlation_id: str | None = None,
        retry_after_s: float | None = None,
    ) -> None:
        """Create the error.

        Args:
            status (int): HTTP status (or a synthetic one: 504 timeout, 503 network).
            message (str): The API's message.
            code (str | None): The API's error code, or one of ours (``no_key``, ``timeout``, ``network``).
            correlation_id (str | None): The API's Correlation-ID header, for support.
            retry_after_s (float | None): Seconds from Retry-After.
        """
        super().__init__(message)
        self.status = status
        self.message = message
        self.code = code
        self.correlation_id = correlation_id
        self.retry_after_s = retry_after_s


def error_hint(err: ApiError, api: Api) -> str:
    """What an agent should do about an API error, appended to the error message.

    Args:
        err (ApiError): The error.
        api (Api): Which API raised it.

    Returns:
        str: One sentence of advice, or "".
    """
    if err.code == "archive_unavailable":
        return ""  # the message already says what to do
    if err.status == 401:
        return (
            "The NewsCatcher API key is missing or invalid. Send your key from https://platform.newscatcherapi.com "
            "in the x-api-key header (or Authorization: Bearer <key>) of the MCP connection."
        )
    if err.status == 402:
        return "The credit balance does not cover this call. Nothing was charged. Top up in the NewsCatcher platform."
    if err.status == 403:
        if "another newscatcher product" in err.message.lower():
            return ""  # a key for another product, not a plan limit: the message already says what to do
        if api == "news":
            return (
                "The plan does not include this (for example a larger limit/page_size or an Enterprise field). "
                "Lower the limit or drop the field."
            )
        return "The plan does not include this (mode, rows, companies or schedule). Pick a smaller option."
    if err.status == 404:
        return "Not found: check the id (ids come from earlier tool results)."
    if err.status == 408:
        return "The search ran out of time. Narrow the window, lower page_size or simplify the query, then retry."
    if err.status == 409:
        return "Not ready yet (the run is still going). Wait, then ask again."
    if err.status == 422:
        return "A parameter is invalid. Fix it as the message says; do not retry unchanged."
    if err.status == 429:
        wait = err.retry_after_s if err.retry_after_s is not None else 2
        return f"Rate limited. Wait {wait:g} s and retry."
    if err.status >= 500:
        return "A temporary NewsCatcher error. Retry in a moment."
    return ""


class _Pacer:
    """Spaces out calls to one endpoint within this process (shared by concurrent tool calls)."""

    def __init__(self, interval_s: float) -> None:
        """Create a pacer.

        Args:
            interval_s (float): Minimum seconds between two calls.
        """
        self.interval_s = interval_s
        self._next = 0.0

    async def wait(self) -> None:
        """Wait for this caller's slot."""
        now = time.monotonic()
        at = max(now, self._next)
        self._next = at + self.interval_s
        if at > now:
            await asyncio.sleep(at - now)


# Module-level so every tool call in a warm instance shares it. On serverless each instance has its own; the
# 429 back-off covers what that misses (the limit is organisation-wide anyway).
_PACERS: dict[str, _Pacer] = {"news:/articles": _Pacer(1.05)}


def _clean_query(query: dict[str, Any] | None) -> dict[str, str]:
    """Drop empty values and join lists with commas, as the APIs expect.

    Args:
        query (dict[str, Any] | None): Query parameters.

    Returns:
        dict[str, str]: Parameters ready for the URL.
    """
    out: dict[str, str] = {}
    for key, value in (query or {}).items():
        if value is None or value == "":
            continue
        if isinstance(value, (list, tuple)):
            if value:
                out[key] = ",".join(str(v) for v in value)
        elif isinstance(value, bool):
            out[key] = "true" if value else "false"
        else:
            out[key] = str(value)
    return out


class NewsCatcherClient:
    """One caller's client for one tool call. Use as ``async with NewsCatcherClient(...) as client``."""

    def __init__(
        self,
        config: Config,
        api_key: str | None,
        *,
        tracking_id: str = "",
        integration: str | None = None,
        deadline: float | None = None,
    ) -> None:
        """Create the client.

        Args:
            config (Config): Server settings.
            api_key (str | None): The caller's NewsCatcher key.
            tracking_id (str): Id of the tool call, put on every log line.
            integration (str | None): Client tag for the User-Agent.
            deadline (float | None): ``time.monotonic()`` value after which long tools should stop and answer.
        """
        self.config = config
        self._api_key = api_key
        self.tracking_id = tracking_id
        self.deadline = deadline
        tag = integration or config.integration
        self._user_agent = f"newscatcher-mcp/{VERSION}" + (f" ({tag})" if tag else "")
        self._http: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "NewsCatcherClient":
        """Open the HTTP connection pool.

        Returns:
            NewsCatcherClient: self.
        """
        self._http = httpx.AsyncClient(timeout=self.config.timeout_s)
        return self

    async def __aexit__(self, *exc: object) -> None:
        """Close the HTTP connection pool."""
        if self._http is not None:
            await self._http.aclose()
            self._http = None

    @property
    def has_key(self) -> bool:
        """Whether a key was given."""
        return bool(self._api_key)

    def time_left(self) -> float:
        """Seconds left before the tool call should wrap up (infinite when there is no deadline).

        Returns:
            float: Seconds.
        """
        return float("inf") if self.deadline is None else self.deadline - time.monotonic()

    def _url(self, api: Api, path: str) -> str:
        """Full URL for an API path.

        Args:
            api (Api): Which API.
            path (str): Path starting with ``/``.

        Returns:
            str: The URL.
        """
        base = self.config.news_api_url if api == "news" else self.config.agent_api_url
        return base + path

    async def request(
        self,
        api: Api,
        method: str,
        path: str,
        *,
        query: dict[str, Any] | None = None,
        body: Any = None,
        files: dict[str, Any] | None = None,
        idempotent: bool | None = None,
    ) -> Any:
        """Call the API and return the parsed body.

        Args:
            api (Api): ``news`` or ``agent``.
            method (str): HTTP method.
            path (str): Path starting with ``/``.
            query (dict[str, Any] | None): Query parameters.
            body (Any): JSON body.
            files (dict[str, Any] | None): Multipart files (uploads).
            idempotent (bool | None): Safe to send twice. Default: reads and news searches yes, Agent API writes no.

        Returns:
            Any: Parsed JSON, text for non-JSON bodies, or None for 204.

        Raises:
            ApiError: On any failure, with a status the tools can explain.
        """
        if not self._api_key:
            raise ApiError(401, "No NewsCatcher API key was sent with this request.", "no_key")
        if self._http is None:
            raise RuntimeError("NewsCatcherClient must be used as an async context manager")
        if idempotent is None:
            idempotent = method in ("GET", "DELETE") or api == "news"
        pacer = _PACERS.get(f"{api}:{path}")
        url = self._url(api, path)
        params = _clean_query(query)
        headers = {"x-api-key": self._api_key, "User-Agent": self._user_agent, "Accept": "application/json"}
        attempt = 0
        while True:
            attempt += 1
            if pacer is not None:
                await pacer.wait()
            started = time.monotonic()
            try:
                res = await self._http.request(
                    method,
                    url,
                    params=params or None,
                    json=body if files is None and body is not None else None,
                    files=files,
                    headers=headers,
                )
            except httpx.TimeoutException as exc:
                self._log_call(api, method, path, None, started, attempt, error=type(exc).__name__)
                message = f"NewsCatcher did not answer within {round(self.config.timeout_s)} s."
                raise ApiError(504, message + ("" if idempotent else MAY_HAVE_GONE_THROUGH), "timeout") from exc
            except httpx.TransportError as exc:
                self._log_call(api, method, path, None, started, attempt, error=type(exc).__name__)
                if attempt < 3 and idempotent:
                    await _sleep(0.8 * attempt)
                    continue
                message = f"Could not reach NewsCatcher: {exc}."
                raise ApiError(503, message + ("" if idempotent else MAY_HAVE_GONE_THROUGH), "network") from exc

            correlation_id = res.headers.get("correlation-id")
            self._log_call(api, method, path, res.status_code, started, attempt, correlation_id=correlation_id)
            if res.is_success:
                if res.status_code == 204 or not res.content:
                    return None
                try:
                    return res.json()
                except ValueError:
                    return res.text  # CSV and other non-JSON bodies

            retry_after_s = _retry_after(res.headers.get("retry-after"))
            # 429s come from the organisation-wide rate limit, which other clients on the same key share.
            max_attempts = 6 if res.status_code == 429 else 3
            if res.status_code in RETRYABLE and attempt < max_attempts and (idempotent or res.status_code == 429):
                if res.status_code == 429:
                    base = max(retry_after_s or 1, 1) * 2 ** (attempt - 1)
                else:
                    base = retry_after_s if retry_after_s else float(attempt)
                await _sleep(min(base + random.random() * 0.3, 10.0))
                continue

            message, code = _error_message(res)
            if not idempotent and res.status_code >= 502:
                message += MAY_HAVE_GONE_THROUGH
            raise ApiError(res.status_code, message[:800], code, correlation_id, retry_after_s)

    def _log_call(
        self,
        api: Api,
        method: str,
        path: str,
        status: int | None,
        started: float,
        attempt: int,
        *,
        correlation_id: str | None = None,
        error: str | None = None,
    ) -> None:
        """Log one upstream HTTP call (path only: query strings and bodies carry user content).

        Args:
            api (Api): Which API.
            method (str): HTTP method.
            path (str): Path.
            status (int | None): HTTP status, None on a transport error.
            started (float): ``time.monotonic()`` at the start.
            attempt (int): Attempt number.
            correlation_id (str | None): The API's Correlation-ID.
            error (str | None): Exception class name on a transport error.
        """
        extra = {
            "tracking_id": self.tracking_id,
            "api": api,
            "method": method,
            "path": path,
            "status_code": status,
            "duration_ms": int((time.monotonic() - started) * 1000),
            "attempt": attempt,
            "correlation_id": correlation_id,
        }
        if error:
            extra["error"] = error
        if status is None or status >= 400:
            logger.warning("NewsCatcher API call failed", extra=extra)
        else:
            logger.debug("NewsCatcher API call succeeded", extra=extra)

    async def get(self, api: Api, path: str, query: dict[str, Any] | None = None) -> Any:
        """GET a path.

        Args:
            api (Api): Which API.
            path (str): Path.
            query (dict[str, Any] | None): Query parameters.

        Returns:
            Any: Parsed body.
        """
        return await self.request(api, "GET", path, query=query)

    async def post(self, api: Api, path: str, body: Any = None, **kwargs: Any) -> Any:
        """POST a JSON body.

        Args:
            api (Api): Which API.
            path (str): Path.
            body (Any): JSON body.
            **kwargs (Any): Passed to ``request`` (``files``, ``idempotent``).

        Returns:
            Any: Parsed body.
        """
        return await self.request(api, "POST", path, body=body, **kwargs)

    async def patch(self, api: Api, path: str, body: Any) -> Any:
        """PATCH a JSON body.

        Args:
            api (Api): Which API.
            path (str): Path.
            body (Any): JSON body.

        Returns:
            Any: Parsed body.
        """
        return await self.request(api, "PATCH", path, body=body)

    async def delete(self, api: Api, path: str) -> Any:
        """DELETE a path.

        Args:
            api (Api): Which API.
            path (str): Path.

        Returns:
            Any: Parsed body.
        """
        return await self.request(api, "DELETE", path)


def _retry_after(raw: str | None) -> float | None:
    """Parse a Retry-After header given in seconds.

    Args:
        raw (str | None): Header value.

    Returns:
        float | None: Seconds, or None.
    """
    try:
        value = float(raw) if raw else None
    except ValueError:
        return None
    return value if value and value > 0 else None


def _error_message(res: httpx.Response) -> tuple[str, str | None]:
    """Pull the message and code out of an error response.

    Args:
        res (httpx.Response): The response.

    Returns:
        tuple[str, str | None]: Message and code.
    """
    text = res.text or res.reason_phrase or ""
    message: Any = text
    code: str | None = None
    try:
        body = json.loads(text)
    except ValueError:
        return text, None
    if isinstance(body, dict):
        message = body.get("message") or body.get("detail") or text
        raw_code = body.get("code") or body.get("status")
        code = str(raw_code) if raw_code is not None else None
    if not isinstance(message, str):
        message = json.dumps(message)
    return message, code
