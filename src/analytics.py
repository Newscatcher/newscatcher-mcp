"""Optional PostHog MCP analytics, as in the NewsMCP server, configured like agent-service.

Self-disabling: without ``POSTHOG_PROJECT_API_KEY``, or with ``POSTHOG_ENABLED=false``, nothing is sent. Every event
carries ``app`` (``POSTHOG_APP``, default ``newscatcher-mcp``) and ``environment`` (``POSTHOG_ENVIRONMENT``, else
Vercel's ``VERCEL_TARGET_ENV``, else ``local``), so one PostHog project can hold several apps and environments.
Analytics observes and never shapes the tool
contract: ``context``, ``enable_conversation_id`` and ``report_missing`` are pinned off because each would add an
argument or a tool that callers see.

Callers are pseudonymised with an HMAC of their API key salted by ``POSTHOG_IDENTITY_SALT``: never the raw key, and
never a reversible encryption of it. Without a salt, sessions stay anonymous.
"""

from __future__ import annotations

import hashlib
import hmac
import os
from typing import Any

from fastmcp import FastMCP

from src.auth import resolve_key
from src.config import Config
from src.log import setup_logging

logger = setup_logging(__name__)


def posthog_settings() -> dict[str, Any]:
    """Read the PostHog env vars (same names and defaults as agent-service).

    Returns:
        dict[str, Any]: ``enabled``, ``project_key``, ``host_url``, ``app``, ``environment``, ``salt``.
    """
    host = (os.getenv("POSTHOG_HOST") or "us.i.posthog.com").strip().removeprefix("https://").removeprefix("http://").rstrip("/")
    port = (os.getenv("POSTHOG_PORT") or "443").strip()
    return {
        "enabled": (os.getenv("POSTHOG_ENABLED") or "true").strip().lower() == "true",
        "project_key": (os.getenv("POSTHOG_PROJECT_API_KEY") or "").strip(),
        "host_url": f"https://{host}" + ("" if port in ("", "443") else f":{port}"),
        "app": (os.getenv("POSTHOG_APP") or "newscatcher-mcp").strip(),
        "environment": (os.getenv("POSTHOG_ENVIRONMENT") or os.getenv("VERCEL_TARGET_ENV") or "local").strip(),
        "salt": (os.getenv("POSTHOG_IDENTITY_SALT") or "").strip(),
    }


def _identity_digest(key: str, salt: str) -> str:
    """HMAC-SHA256 of a key, so the same caller maps to the same id without the key being recoverable.

    Args:
        key (str): API key.
        salt (str): Server-side secret.

    Returns:
        str: ``key_<hex>`` (first 32 hex chars).
    """
    return "key_" + hmac.new(salt.encode(), key.encode(), hashlib.sha256).hexdigest()[:32]


def init_analytics(mcp: FastMCP, config: Config) -> Any | None:
    """Instrument the server for PostHog when a project key is configured. Must run before the ASGI app is built.

    Args:
        mcp (FastMCP): The server.
        config (Config): Server settings.

    Returns:
        Any | None: The PostHog client to flush per request, or None when analytics are off.
    """
    settings = posthog_settings()
    if not settings["enabled"]:
        logger.info("PostHog MCP analytics disabled: POSTHOG_ENABLED is false")
        return None
    if not settings["project_key"]:
        logger.info("PostHog MCP analytics disabled: POSTHOG_PROJECT_API_KEY is not set")
        return None
    salt = settings["salt"]

    async def identify(request: dict[str, Any], extra: dict[str, Any] | None = None) -> Any:
        """Pseudonymous caller id for PostHog.

        Args:
            request (dict[str, Any]): The MCP request (unused).
            extra (dict[str, Any] | None): Extra info (unused).

        Returns:
            Any: A UserIdentity, or None to stay anonymous.
        """
        from posthog.mcp import UserIdentity

        key = resolve_key(config)
        if not key or not salt:
            return None
        return UserIdentity(distinct_id=_identity_digest(key, salt), properties={"auth": "keyed"})

    try:
        from posthog import Client
        from posthog.mcp import MCPAnalyticsOptions, instrument

        client = Client(
            settings["project_key"],
            host=settings["host_url"],
            super_properties={"app": settings["app"], "environment": settings["environment"]},
        )
        instrument(
            mcp,
            client,
            MCPAnalyticsOptions(context=False, enable_conversation_id=False, report_missing=False, identify=identify),
        )
    except Exception as exc:  # noqa: BLE001 - analytics must never take the server down
        logger.warning("PostHog MCP analytics could not be initialized; serving without it", extra={"error": str(exc)[:300]})
        return None
    logger.info(
        "PostHog MCP analytics enabled",
        extra={
            "posthog_host": settings["host_url"],
            "app": settings["app"],
            "environment": settings["environment"],
            "pseudonymous_ids": bool(salt),
        },
    )
    return client


class AnalyticsFlushMiddleware:
    """Flush queued analytics events at the end of each HTTP request (a frozen serverless instance never would)."""

    def __init__(self, app: Any, client: Any) -> None:
        """Wrap an ASGI app.

        Args:
            app (Any): The ASGI app.
            client (Any): PostHog client.
        """
        self.app = app
        self.client = client

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        """Handle one ASGI event, then flush.

        Args:
            scope (dict[str, Any]): ASGI scope.
            receive (Any): ASGI receive.
            send (Any): ASGI send.
        """
        try:
            await self.app(scope, receive, send)
        finally:
            if scope.get("type") == "http":
                try:
                    self.client.flush()
                except Exception as exc:  # noqa: BLE001 - never fail a request over analytics
                    logger.warning("PostHog event flush failed", extra={"error": str(exc)[:300]})
