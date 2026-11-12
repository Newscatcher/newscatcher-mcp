"""Sign-in with a NewsCatcher platform account: OAuth discovery, client registration, and token → API key.

An MCP client (Claude, ChatGPT, Cursor…) that gets a 401 from ``/mcp`` reads the ``resource_metadata`` URL in
``WWW-Authenticate``, discovers the authorization server, registers itself, sends the user to sign in and approve,
and comes back with an access token. Supabase Auth is the authorization server: the user signs in there and the
client collects its token there, so no password, code or token passes through this server except the access token
on each MCP request. Two things are served from here instead of Supabase, because real clients fail without them:

- The protected-resource document names THIS server as the authorization server, and this server serves Supabase's
  authorization-server metadata with ``issuer`` and ``registration_endpoint`` rewritten to itself. A client asks
  whoever the protected-resource document names where to register, so naming Supabase would skip the next point.
- Registration is proxied so a client that names no ``token_endpoint_auth_method`` is registered as a public client
  (``none``). The RFC 7591 default is ``client_secret_basic``, which a client holding no secret cannot complete.

Documents are served at every path clients check (path-suffixed and bare, OAuth and OIDC names), with URLs written
as plain strings: a trailing slash on an origin makes clients request ``//.well-known/...``.

The access token names a person; the APIs want a workspace's API key. The platform API resolves the token the way
the platform app does: list the user's workspaces, pick the default one, list its keys, reveal the Default API Key.
That call also validates the token (the platform API rejects a bad, expired or revoked one), so this server holds no
signing secret and verifies nothing itself. The key is cached in memory for a few minutes per token, keyed by the
token's SHA-256; neither the token nor the key is ever logged.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import time
from typing import Any

import httpx
from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from src.config import OAuthConfig
from src.log import setup_logging

logger = setup_logging(__name__)

MCP_PATH = "/mcp"
REGISTER_PATH = "/oauth/register"
PLATFORM_URL = "https://platform.newscatcherapi.com"
KEY_TTL_S = 300.0
METADATA_TTL_S = 600.0
MAX_CACHED_KEYS = 1024
MAX_REGISTRATION_BYTES = 65_536
GATEWAY_TIMEOUT_S = 15.0
DEFAULT_KEY_NAME = "default api key"
PERSONAL_WORKSPACE = "personal"

_keys: dict[str, tuple[str, float]] = {}
_inflight: dict[str, asyncio.Future[str]] = {}
_metadata: tuple[dict[str, Any], float] | None = None


async def _sleep(seconds: float) -> None:
    """Wait (patched out in tests).

    Args:
        seconds (float): How long.
    """
    await asyncio.sleep(seconds)


class TokenRejected(Exception):
    """The platform does not accept the access token (bad, expired or revoked): the client must sign in again."""


class SignInError(Exception):
    """The token is fine but no API key can be had for it; the message tells the user what to do."""


def looks_like_jwt(value: str) -> bool:
    """Whether a Bearer value is an access token rather than an API key, judged by its shape.

    A platform access token is a JWT: three base64url parts, the first starting ``eyJ`` (``{"``). An API key has no
    dots. Deciding by shape, not by configuration, means a misconfigured deployment never mistakes a key for a token.

    Args:
        value (str): The Bearer value.

    Returns:
        bool: True for a JWT.
    """
    parts = value.split(".")
    return len(parts) == 3 and value.startswith("eyJ") and all(parts)


def _claims(token: str) -> dict[str, Any]:
    """The (unverified) payload of a JWT, for the ``x-user-email`` header the platform API expects.

    Nothing is trusted from it: the platform API validates the token itself.

    Args:
        token (str): The JWT.

    Returns:
        dict[str, Any]: The claims, or {} when unreadable.
    """
    try:
        payload = token.split(".")[1]
        data = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    except (IndexError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def resource_metadata_url(oauth: OAuthConfig) -> str:
    """URL of this server's protected-resource document (RFC 9728, path-suffixed form).

    Args:
        oauth (OAuthConfig): Sign-in settings.

    Returns:
        str: The URL.
    """
    return f"{oauth.public_url}/.well-known/oauth-protected-resource{MCP_PATH}"


def www_authenticate(oauth: OAuthConfig | None, error: str | None = None) -> bytes:
    """The ``WWW-Authenticate`` value for a 401: where to sign in, when sign-in is on.

    Args:
        oauth (OAuthConfig | None): Sign-in settings.
        error (str | None): RFC 6750 error code, e.g. ``invalid_token``.

    Returns:
        bytes: The header value.
    """
    parts = ['Bearer realm="newscatcher"']
    if error:
        parts.append(f'error="{error}"')
    if oauth is not None:
        parts.append(f'resource_metadata="{resource_metadata_url(oauth)}"')
    return ", ".join(parts).encode()


def pick_workspace(organizations: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The workspace the platform app opens by default: the first not named "Personal", else the default one.

    Args:
        organizations (list[dict[str, Any]]): ``organizations`` from ``GET /user/organizations``.

    Returns:
        dict[str, Any] | None: The workspace, or None when there is none.
    """
    orgs = [o for o in organizations if isinstance(o, dict) and o.get("organization_id")]
    named = next((o for o in orgs if str(o.get("organization_name") or "").strip().lower() != PERSONAL_WORKSPACE), None)
    return named or next((o for o in orgs if o.get("is_default")), None) or (orgs[0] if orgs else None)


def pick_default_key(keys: list[dict[str, Any]]) -> dict[str, Any] | None:
    """A workspace's Default API Key: the enabled key named so at sign-up, else the oldest enabled key.

    Args:
        keys (list[dict[str, Any]]): ``api_keys`` from ``GET /user/api_key/list``.

    Returns:
        dict[str, Any] | None: The key entry, or None when no key is enabled.
    """
    enabled = [k for k in keys if isinstance(k, dict) and k.get("api_key_status") == "enabled" and k.get("api_key_id") is not None]
    named = next((k for k in enabled if str(k.get("name") or "").strip().lower() == DEFAULT_KEY_NAME), None)
    return named or min(enabled, key=lambda k: str(k.get("created_at") or ""), default=None)


async def _gateway(client: httpx.AsyncClient, method: str, path: str, headers: dict[str, str], body: Any = None) -> Any:
    """Call the platform API and return its JSON, mapping failures to TokenRejected / SignInError.

    Args:
        client (httpx.AsyncClient): HTTP client.
        method (str): HTTP method.
        path (str): Path, e.g. ``/user/organizations``.
        headers (dict[str, str]): Auth headers.
        body (Any): JSON body.

    Returns:
        Any: The decoded JSON.

    Raises:
        TokenRejected: On 401.
        SignInError: On any other failure.
    """
    for attempt in range(2):
        try:
            response = await client.request(method, path, headers=headers, json=body)
        except httpx.HTTPError as err:
            logger.warning("Platform API unreachable", extra={"path": path, "error": type(err).__name__})
            raise SignInError("The NewsCatcher platform could not be reached to look up your API key. Try again.") from err
        # The reveal endpoint allows about one call a second per user: wait once, then give up.
        if response.status_code == 429 and attempt == 0:
            await _sleep(1.1)
            continue
        break
    if response.status_code == 401:
        # Enough to tell an expired token from one the platform does not accept at all; never the token itself.
        claims = _claims(headers.get("Authorization", "").removeprefix("Bearer "))
        try:
            detail = str(response.json().get("detail") or "")[:200]
        except (ValueError, AttributeError):
            detail = ""
        logger.warning(
            "Platform API rejected the access token",
            extra={
                "path": path,
                "detail": detail,
                "issued_to_client": "client_id" in claims,
                "expired": isinstance(claims.get("exp"), (int, float)) and claims["exp"] < time.time(),
            },
        )
        raise TokenRejected()
    if response.status_code >= 400:
        logger.warning("Platform API refused the key lookup", extra={"path": path, "status": response.status_code})
        raise SignInError(
            "Your NewsCatcher API key could not be looked up right now. Try again, or connect with an API key "
            f"from {PLATFORM_URL} in the x-api-key header."
        )
    try:
        return response.json()
    except ValueError as err:
        raise SignInError("The NewsCatcher platform gave an unreadable answer. Try again.") from err


async def _lookup_key(oauth: OAuthConfig, token: str) -> str:
    """Resolve an access token to the API key of the user's default workspace.

    Args:
        oauth (OAuthConfig): Sign-in settings.
        token (str): The access token.

    Returns:
        str: The API key.

    Raises:
        TokenRejected: The token is not accepted.
        SignInError: No key can be had for this user.
    """
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    email = _claims(token).get("email")
    if isinstance(email, str) and email:
        headers["x-user-email"] = email
    async with httpx.AsyncClient(base_url=oauth.platform_api_url, timeout=GATEWAY_TIMEOUT_S) as client:
        orgs = await _gateway(client, "GET", "/user/organizations", headers)
        workspace = pick_workspace(orgs.get("organizations") or [] if isinstance(orgs, dict) else [])
        if workspace is None:
            raise SignInError(f"Your NewsCatcher account is not set up yet. Open {PLATFORM_URL} once to finish, then try again.")
        headers["x-organization-id"] = str(workspace["organization_id"])
        listed = await _gateway(client, "GET", "/user/api_key/list", headers)
        entry = pick_default_key(listed.get("api_keys") or [] if isinstance(listed, dict) else [])
        if entry is None:
            raise SignInError(f"Your NewsCatcher workspace has no enabled API key. Create one at {PLATFORM_URL}, then try again.")
        revealed = await _gateway(client, "POST", "/user/api_key/reveal", headers, {"api_key_id": entry["api_key_id"]})
    key = str((revealed or {}).get("api_key") or "").strip() if isinstance(revealed, dict) else ""
    if not key:
        raise SignInError(f"Your NewsCatcher API key could not be read. Connect with a key from {PLATFORM_URL} in the x-api-key header.")
    return key


async def key_for_token(oauth: OAuthConfig, token: str) -> str:
    """The API key for an access token, cached per token and looked up once even under concurrent requests.

    An MCP client sends several requests at once on connect (initialize, tools/list…); one lookup serves them all,
    which also keeps the platform's one-reveal-a-second limit from refusing the rest. Failures are not cached.

    Args:
        oauth (OAuthConfig): Sign-in settings.
        token (str): The access token.

    Returns:
        str: The API key.

    Raises:
        TokenRejected: The token is not accepted.
        SignInError: No key can be had for this user.
    """
    digest = hashlib.sha256(token.encode()).hexdigest()
    now = time.monotonic()
    cached = _keys.get(digest)
    if cached and cached[1] > now:
        return cached[0]
    pending = _inflight.get(digest)
    if pending is None or pending.get_loop() is not asyncio.get_running_loop():
        pending = asyncio.ensure_future(_lookup_key(oauth, token))
        _inflight[digest] = pending
        pending.add_done_callback(lambda _: _inflight.pop(digest, None))
    key = await asyncio.shield(pending)
    if len(_keys) >= MAX_CACHED_KEYS:
        for stale in [d for d, (_, exp) in _keys.items() if exp <= now] or list(_keys)[: MAX_CACHED_KEYS // 4]:
            _keys.pop(stale, None)
    _keys[digest] = (key, now + KEY_TTL_S)
    return key


def clear_caches() -> None:
    """Forget cached keys and metadata (tests)."""
    global _metadata
    _keys.clear()
    _inflight.clear()
    _metadata = None


async def _authorization_server_metadata(oauth: OAuthConfig) -> dict[str, Any]:
    """Supabase's authorization-server metadata with ``issuer`` and ``registration_endpoint`` pointing here.

    Authorization and token endpoints keep pointing at Supabase, so the user signs in there and the client collects
    its token there. Cached for a few minutes: discovery runs on every new connection.

    Args:
        oauth (OAuthConfig): Sign-in settings.

    Returns:
        dict[str, Any]: The document.

    Raises:
        httpx.HTTPError: Supabase unreachable or erroring.
    """
    global _metadata
    if _metadata and _metadata[1] > time.monotonic():
        return dict(_metadata[0])
    async with httpx.AsyncClient(timeout=GATEWAY_TIMEOUT_S) as client:
        response = await client.get(f"{oauth.supabase_url}/auth/v1/.well-known/oauth-authorization-server")
        response.raise_for_status()
        doc = response.json()
    # RFC 8414: a document served from here names here as its issuer.
    doc["issuer"] = oauth.public_url
    doc["registration_endpoint"] = f"{oauth.public_url}{REGISTER_PATH}"
    _metadata = (doc, time.monotonic() + METADATA_TTL_S)
    return dict(doc)


def register_oauth_routes(mcp: FastMCP, oauth: OAuthConfig) -> None:
    """Serve discovery, client registration, and a root page naming the MCP endpoint.

    Args:
        mcp (FastMCP): The server.
        oauth (OAuthConfig): Sign-in settings.
    """

    async def protected_resource(request: Request) -> JSONResponse:
        """RFC 9728 protected-resource metadata: this resource, and this server as where to sign in.

        Args:
            request (Request): The HTTP request.

        Returns:
            JSONResponse: The document.
        """
        return JSONResponse(
            {
                "resource": f"{oauth.public_url}{MCP_PATH}",
                "authorization_servers": [oauth.public_url],
                "bearer_methods_supported": ["header"],
                "resource_name": "NewsCatcher",
                "resource_documentation": "https://www.newscatcherapi.com",
            }
        )

    async def authorization_server(request: Request) -> JSONResponse:
        """RFC 8414 authorization-server metadata (served under both the OAuth and the OIDC name).

        Args:
            request (Request): The HTTP request.

        Returns:
            JSONResponse: The document, or 502 when Supabase cannot be read.
        """
        try:
            return JSONResponse(await _authorization_server_metadata(oauth))
        except (httpx.HTTPError, ValueError) as err:
            logger.warning("Authorization server metadata unavailable", extra={"error": type(err).__name__})
            return JSONResponse(
                {"error": "temporarily_unavailable", "error_description": "Sign-in settings could not be read. Try again."},
                status_code=502,
            )

    async def register(request: Request) -> JSONResponse:
        """RFC 7591 dynamic client registration, forwarded to Supabase as a public client unless asked otherwise.

        Args:
            request (Request): The HTTP request.

        Returns:
            JSONResponse: Supabase's answer.
        """
        raw = await request.body()
        if len(raw) > MAX_REGISTRATION_BYTES:
            return JSONResponse({"error": "invalid_client_metadata", "error_description": "Body too large."}, status_code=413)
        try:
            body = json.loads(raw)
        except ValueError:
            body = None
        if not isinstance(body, dict):
            return JSONResponse(
                {"error": "invalid_client_metadata", "error_description": "Body must be a JSON object."}, status_code=400
            )
        # Only silence is overridden: a client that asked for a secret knows how to use one.
        if not body.get("token_endpoint_auth_method"):
            body["token_endpoint_auth_method"] = "none"
        try:
            async with httpx.AsyncClient(timeout=GATEWAY_TIMEOUT_S) as client:
                upstream = await client.post(f"{oauth.supabase_url}/auth/v1/oauth/clients/register", json=body)
            payload = upstream.json()
        except (httpx.HTTPError, ValueError) as err:
            logger.warning("Client registration failed upstream", extra={"error": type(err).__name__})
            return JSONResponse(
                {"error": "temporarily_unavailable", "error_description": "Registration is unavailable. Try again."},
                status_code=502,
            )
        # Never log the body: a confidential registration carries a client secret.
        logger.info(
            "Client registration forwarded",
            extra={"status": upstream.status_code, "public_client": body["token_endpoint_auth_method"] == "none"},
        )
        return JSONResponse(payload, status_code=upstream.status_code)

    async def root(request: Request) -> JSONResponse:
        """Name the MCP endpoint: a connector set up with the bare host signs in fine, then finds no server.

        Args:
            request (Request): The HTTP request.

        Returns:
            JSONResponse: Where to connect.
        """
        return JSONResponse({"name": "NewsCatcher MCP", "mcp_endpoint": f"{oauth.public_url}{MCP_PATH}"})

    for path in (f"/.well-known/oauth-protected-resource{MCP_PATH}", "/.well-known/oauth-protected-resource"):
        mcp.custom_route(path, methods=["GET"])(protected_resource)
    for path in ("/.well-known/oauth-authorization-server", "/.well-known/openid-configuration"):
        mcp.custom_route(path, methods=["GET"])(authorization_server)
    mcp.custom_route(REGISTER_PATH, methods=["POST"])(register)
    mcp.custom_route("/", methods=["GET"])(root)
