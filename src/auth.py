"""Who is calling: the caller's API key and per-connection options, read from the current HTTP request.

The hosted server serves many users from one deployment, so every request carries its own NewsCatcher key in
``x-api-key`` or ``Authorization: Bearer``. There is deliberately no fallback to a server-side key over HTTP: a
request without a key must never be billed to someone else. ``?apiKey=`` on the URL is accepted only when the
operator opts in (``NEWSCATCHER_ALLOW_KEY_IN_URL=1``), because URLs end up in access logs.

With sign-in on (``NEWSCATCHER_OAUTH``, see ``src/oauth.py``), a Bearer value shaped like a JWT is a platform
access token instead: the middleware exchanges it for the user's workspace key once per request and leaves the key on
the request state, where ``resolve_key`` finds it. API keys work exactly as before.

Outside an HTTP request (local stdio, tests) the key comes from ``NEWSCATCHER_API_KEY``.
"""

from __future__ import annotations

import json
import os
from typing import Any

from starlette.requests import Request

from src.config import Config, clean_integration, parse_toolsets
from src.oauth import SignInError, TokenRejected, key_for_token, looks_like_jwt, www_authenticate

MAX_BODY_BYTES = 1_048_576
STATE_KEY = "newscatcher_key"
STATE_PROBLEM = "newscatcher_sign_in_problem"


def current_request() -> Request | None:
    """The HTTP request being served, or None outside HTTP (stdio, in-process tests).

    Returns:
        Request | None: The Starlette request.
    """
    try:
        from fastmcp.server.dependencies import get_http_request

        return get_http_request()
    except RuntimeError:
        return None


def _bearer(value: str | None) -> str | None:
    """Extract the token of a case-insensitive ``Bearer <token>`` header.

    Args:
        value (str | None): Authorization header.

    Returns:
        str | None: The token.
    """
    if not value:
        return None
    scheme, _, token = value.strip().partition(" ")
    if scheme.lower() != "bearer":
        return None
    return token.strip() or None


def key_from_headers(headers: Any, query: Any, allow_key_in_url: bool) -> str | None:
    """Find the caller's key in request headers (and the URL when allowed).

    Args:
        headers (Any): Case-insensitive header mapping.
        query (Any): Query parameter mapping.
        allow_key_in_url (bool): Whether ``?apiKey=`` is accepted.

    Returns:
        str | None: The key.
    """
    key = (headers.get("x-api-key") or "").strip() or _bearer(headers.get("authorization"))
    if not key and allow_key_in_url:
        key = (query.get("apiKey") or "").strip() or None
    return key or None


def platform_token(headers: Any, config: Config) -> str | None:
    """The caller's platform access token, when sign-in is on and the Bearer value is one (not an API key).

    ``x-api-key`` wins over ``Authorization``, as for keys, so a caller sending both keeps today's behaviour.

    Args:
        headers (Any): Case-insensitive header mapping.
        config (Config): Server settings.

    Returns:
        str | None: The token.
    """
    if config.oauth is None or (headers.get("x-api-key") or "").strip():
        return None
    token = _bearer(headers.get("authorization"))
    return token if token and looks_like_jwt(token) else None


def resolve_key(config: Config) -> str | None:
    """The NewsCatcher key for the current tool call.

    Args:
        config (Config): Server settings.

    Returns:
        str | None: The key, or None when the caller sent none (or a token no key could be found for).
    """
    request = current_request()
    if request is None:
        return (os.getenv("NEWSCATCHER_API_KEY") or "").strip() or None
    state = request.scope.get("state") or {}
    if STATE_KEY in state:
        return state[STATE_KEY]
    if platform_token(request.headers, config):
        return None  # a token is never forwarded as a key
    return key_from_headers(request.headers, request.query_params, config.allow_key_in_url)


def sign_in_problem() -> str | None:
    """Why a signed-in caller has no key (no workspace yet, platform unreachable…), to show instead of a 401 hint.

    Returns:
        str | None: The message, or None.
    """
    request = current_request()
    return (request.scope.get("state") or {}).get(STATE_PROBLEM) if request is not None else None


def request_toolsets(config: Config) -> frozenset[str]:
    """Toolsets for this connection: ``?tools=news,research`` on the MCP URL, else the server default.

    Args:
        config (Config): Server settings.

    Returns:
        frozenset[str]: Toolset names.
    """
    request = current_request()
    raw = request.query_params.get("tools") if request is not None else None
    return parse_toolsets(raw) if raw else config.toolsets


def request_integration(config: Config) -> str | None:
    """Client tag for usage attribution: ``?client=cursor`` on the MCP URL, else the server default.

    Args:
        config (Config): Server settings.

    Returns:
        str | None: The tag.
    """
    request = current_request()
    raw = request.query_params.get("client") if request is not None else None
    return clean_integration(raw) or config.integration


class RequireCredentialsMiddleware:
    """ASGI middleware: refuse MCP POSTs without a key or a valid platform token (401), and bodies over 1 MiB (413).

    The 401 carries ``WWW-Authenticate``; with sign-in on it also names the protected-resource document, which is
    what makes MCP clients offer to connect with an account. A token the platform rejects gets ``invalid_token`` so
    the client refreshes it. A valid token with no key behind it (account not set up, platform unreachable) passes
    through, and tool calls answer with what to do. Only POST is checked: a client's GET for the event stream must
    never read as a sign-in demand.
    """

    def __init__(self, app: Any, config: Config, mcp_path: str = "/mcp") -> None:
        """Wrap an ASGI app.

        Args:
            app (Any): The ASGI app.
            config (Config): Server settings.
            mcp_path (str): Path of the MCP endpoint.
        """
        self.app = app
        self.config = config
        self.mcp_path = mcp_path.rstrip("/")

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        """Handle one ASGI event.

        Args:
            scope (dict[str, Any]): ASGI scope.
            receive (Any): ASGI receive.
            send (Any): ASGI send.
        """
        if scope.get("type") != "http" or scope.get("method") != "POST" or scope.get("path", "").rstrip("/") != self.mcp_path:
            await self.app(scope, receive, send)
            return
        request = Request(scope)
        length = request.headers.get("content-length")
        if length and length.isdigit() and int(length) > MAX_BODY_BYTES:
            await _respond(send, 413, {"error": "Request body over 1 MiB."})
            return
        oauth = self.config.oauth
        token = platform_token(request.headers, self.config)
        if token is not None and oauth is not None:
            state = scope.setdefault("state", {})
            try:
                state[STATE_KEY] = await key_for_token(oauth, token)
            except TokenRejected:
                await _respond(
                    send,
                    401,
                    {"error": "The sign-in has expired or was revoked. Reconnect to NewsCatcher."},
                    extra_headers=[(b"www-authenticate", www_authenticate(oauth, "invalid_token"))],
                )
                return
            except SignInError as err:
                state[STATE_KEY] = None
                state[STATE_PROBLEM] = str(err)
        elif not key_from_headers(request.headers, request.query_params, self.config.allow_key_in_url):
            hint = "Connect with your NewsCatcher account, or send" if oauth is not None else "Send"
            await _respond(
                send,
                401,
                {
                    "error": f"{hint} your NewsCatcher API key in the x-api-key header (or Authorization: Bearer <key>). "
                    "Get a key at https://platform.newscatcherapi.com"
                },
                extra_headers=[(b"www-authenticate", www_authenticate(oauth))],
            )
            return
        await self.app(scope, receive, send)


async def _respond(send: Any, status: int, body: dict[str, Any], extra_headers: list[tuple[bytes, bytes]] | None = None) -> None:
    """Send a small JSON response.

    Args:
        send (Any): ASGI send.
        status (int): HTTP status.
        body (dict[str, Any]): JSON body.
        extra_headers (list[tuple[bytes, bytes]] | None): More headers.
    """
    payload = json.dumps(body).encode()
    headers = [(b"content-type", b"application/json"), (b"content-length", str(len(payload)).encode())]
    await send({"type": "http.response.start", "status": status, "headers": headers + (extra_headers or [])})
    await send({"type": "http.response.body", "body": payload})
