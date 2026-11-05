"""Who is calling: the caller's API key and per-connection options, read from the current HTTP request.

The hosted server serves many users from one deployment, so every request carries its own NewsCatcher key in
``x-api-key`` or ``Authorization: Bearer``. There is deliberately no fallback to a server-side key over HTTP: a
request without a key must never be billed to someone else. ``?apiKey=`` on the URL is accepted only when the
operator opts in (``NEWSCATCHER_ALLOW_KEY_IN_URL=1``), because URLs end up in access logs.

Outside an HTTP request (local stdio, tests) the key comes from ``NEWSCATCHER_API_KEY``.
"""

from __future__ import annotations

import json
import os
from typing import Any

from starlette.requests import Request

from src.config import Config, clean_integration, parse_toolsets

MAX_BODY_BYTES = 1_048_576


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


def resolve_key(config: Config) -> str | None:
    """The NewsCatcher key for the current tool call.

    Args:
        config (Config): Server settings.

    Returns:
        str | None: The key, or None when the caller sent none.
    """
    request = current_request()
    if request is None:
        return (os.getenv("NEWSCATCHER_API_KEY") or "").strip() or None
    return key_from_headers(request.headers, request.query_params, config.allow_key_in_url)


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


class RequireApiKeyMiddleware:
    """ASGI middleware: refuse MCP POSTs without a key (401) and bodies over 1 MiB (413).

    The 401 carries ``WWW-Authenticate`` so clients can tell the user what is missing. OAuth will replace this
    check later; until then a key per request is the only way in.
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
        if not key_from_headers(request.headers, request.query_params, self.config.allow_key_in_url):
            await _respond(
                send,
                401,
                {
                    "error": "Send your NewsCatcher API key in the x-api-key header (or Authorization: Bearer <key>). "
                    "Get a key at https://platform.newscatcherapi.com"
                },
                extra_headers=[(b"www-authenticate", b'Bearer realm="newscatcher"')],
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
