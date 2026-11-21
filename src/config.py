"""Settings read from the environment.

The hosted server never holds a NewsCatcher key of its own: every HTTP request brings the caller's key. Only the
local stdio mode (development) reads ``NEWSCATCHER_API_KEY``.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

from src.log import setup_logging

TOOLSETS: tuple[str, ...] = ("news", "research", "lists", "monitors")


def parse_toolsets(raw: str | None) -> frozenset[str]:
    """Parse a comma-separated toolset list; empty, ``all`` or nothing valid means every toolset.

    Args:
        raw (str | None): e.g. ``"news,research"``.

    Returns:
        frozenset[str]: The toolsets to expose.
    """
    if not raw or not raw.strip() or raw.strip().lower() == "all":
        return frozenset(TOOLSETS)
    wanted = {s.strip().lower() for s in raw.split(",") if s.strip()}
    valid = wanted & set(TOOLSETS)
    return frozenset(valid) if valid else frozenset(TOOLSETS)


def clean_integration(raw: str | None) -> str | None:
    """Sanitise an integration/client tag for the User-Agent (word chars, dot, dash; 40 chars).

    Args:
        raw (str | None): The tag as given.

    Returns:
        str | None: The cleaned tag, or None when nothing is left.
    """
    if not raw:
        return None
    cleaned = re.sub(r"[^\w.\-]", "", raw)[:40]
    return cleaned or None


def _env_int(name: str, default: int) -> int:
    """Read a positive integer env var.

    Args:
        name (str): Variable name.
        default (int): Value when unset or invalid.

    Returns:
        int: The value.
    """
    try:
        value = int(os.getenv(name, ""))
    except ValueError:
        return default
    return value if value > 0 else default


@dataclass(frozen=True)
class OAuthConfig:
    """Sign-in with a NewsCatcher platform account (OAuth 2.1, Supabase Auth as the authorization server).

    ``public_url`` is this deployment's own origin (``https://host``, no path, no trailing slash): it goes verbatim
    into the discovery documents, so a client builds its next URL from it. ``supabase_url`` is the auth project that
    signs users in to the platform; ``platform_api_url`` is the platform API that exchanges a signed-in user's token for
    their workspace's API key.
    """

    public_url: str
    supabase_url: str
    platform_api_url: str


@dataclass(frozen=True)
class Config:
    """Server settings."""

    news_api_url: str = "https://api.newscatcherapi.com/news-api"
    agent_api_url: str = "https://api.newscatcherapi.com/agent"
    toolsets: frozenset[str] = field(default_factory=lambda: frozenset(TOOLSETS))
    # Per-request timeout for the APIs (high-effort searches take ~30 s).
    timeout_s: float = 90.0
    # Longest a single tool call may keep working (waiting for a run, paging, counting). Keep it below the
    # Vercel function's maxDuration so a call returns a useful partial answer instead of being killed.
    max_call_seconds: int = 240
    # Accept ?apiKey= on the MCP URL. Off by default: URLs end up in access logs.
    allow_key_in_url: bool = False
    integration: str | None = None
    # Sign-in with a platform account; None keeps API keys as the only way in.
    oauth: OAuthConfig | None = None


def service_url(prefix: str, default_host: str, default_endpoint: str) -> str:
    """Build an API base URL from the split env vars ``<prefix>_URL`` (host), ``<prefix>_PORT``, ``<prefix>_ENDPOINT``.

    URLs are split into three variables so a host can be searched for exactly across configs.
    The scheme is always https; port 443 (or no port) is left out of the URL.

    Args:
        prefix (str): e.g. ``NEWSCATCHER_NEWS_API``.
        default_host (str): Host when ``<prefix>_URL`` is unset.
        default_endpoint (str): Path when ``<prefix>_ENDPOINT`` is unset.

    Returns:
        str: e.g. ``https://api.newscatcherapi.com/news-api``.

    Raises:
        ValueError: When ``<prefix>_URL`` holds more than a host (a scheme or a path).
    """
    host = (os.getenv(f"{prefix}_URL") or default_host).strip().rstrip("/")
    if "://" in host or "/" in host:
        raise ValueError(f"{prefix}_URL must be a bare host like api.newscatcherapi.com, got {host!r}")
    port = (os.getenv(f"{prefix}_PORT") or "").strip()
    raw_endpoint = os.getenv(f"{prefix}_ENDPOINT")
    endpoint = (default_endpoint if raw_endpoint is None else raw_endpoint).strip().strip("/")
    return f"https://{host}" + (f":{port}" if port and port != "443" else "") + (f"/{endpoint}" if endpoint else "")


def load_oauth_config() -> OAuthConfig | None:
    """Sign-in settings, when ``NEWSCATCHER_OAUTH=1`` and every value it needs is set.

    All or nothing: with the flag on and a value missing or malformed, the error is logged and the server runs with
    API keys only, because half-configured sign-in (discovery naming the wrong host) is worse than none.
    ``NEWSCATCHER_SUPABASE_URL`` has no default, so a fork or a preview never points at real accounts by accident.

    Returns:
        OAuthConfig | None: The settings, or None when sign-in is off.
    """
    if (os.getenv("NEWSCATCHER_OAUTH") or "").strip().lower() not in {"1", "true", "yes", "on"}:
        return None
    public_url = (os.getenv("NEWSCATCHER_PUBLIC_URL") or "").strip().rstrip("/").removesuffix("/mcp").rstrip("/")
    problems: list[str] = []
    if not re.fullmatch(r"https://[^/\s]+|http://(localhost|127\.0\.0\.1)(:\d+)?", public_url):
        problems.append("NEWSCATCHER_PUBLIC_URL must be this deployment's https origin, e.g. https://mcp.example.com")
    supabase_host = (os.getenv("NEWSCATCHER_SUPABASE_URL") or "").strip()
    if not supabase_host:
        problems.append("NEWSCATCHER_SUPABASE_URL must be the auth project's host, e.g. <ref>.supabase.co")
    try:
        supabase_url = service_url("NEWSCATCHER_SUPABASE", supabase_host, "")
        platform_api_url = service_url("NEWSCATCHER_PLATFORM_API", "platform-api.newscatcherapi.com", "")
    except ValueError as err:
        problems.append(str(err))
    if problems:
        setup_logging(__name__).error(
            "NEWSCATCHER_OAUTH is on but sign-in is misconfigured; running with API keys only",
            extra={"problems": problems},
        )
        return None
    return OAuthConfig(public_url=public_url, supabase_url=supabase_url, platform_api_url=platform_api_url)


def load_config() -> Config:
    """Build the config from environment variables.

    Returns:
        Config: The settings.
    """
    return Config(
        news_api_url=service_url("NEWSCATCHER_NEWS_API", "api.newscatcherapi.com", "news-api"),
        agent_api_url=service_url("NEWSCATCHER_AGENT_API", "api.newscatcherapi.com", "agent"),
        toolsets=parse_toolsets(os.getenv("NEWSCATCHER_TOOLSETS")),
        timeout_s=_env_int("NEWSCATCHER_TIMEOUT_MS", 90_000) / 1000,
        max_call_seconds=_env_int("NEWSCATCHER_MAX_CALL_SECONDS", 240),
        allow_key_in_url=os.getenv("NEWSCATCHER_ALLOW_KEY_IN_URL") == "1",
        integration=clean_integration(os.getenv("NEWSCATCHER_INTEGRATION")),
        oauth=load_oauth_config(),
    )
