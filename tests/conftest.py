"""Shared fixtures: a server per test, upstream HTTP mocked with respx, retries and pacing made instant."""

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import httpx
import pytest
import respx
from fastmcp import Client, FastMCP

from src import client as client_module
from src.config import Config, load_config
from src.server import build_server


@dataclass
class Recorded:
    """One upstream request the server made."""

    url: str
    method: str
    body: Any
    headers: dict[str, str]
    params: dict[str, str] = field(default_factory=dict)


Reply = dict[str, Any]
Responder = Callable[[Recorded], Reply]


@dataclass
class Harness:
    """A server wired to a fake NewsCatcher API."""

    mcp: FastMCP
    calls: list[Recorded]

    async def call(self, name: str, args: dict[str, Any] | None = None) -> tuple[str, bool]:
        """Call a tool through a real MCP client (in-process).

        Args:
            name (str): Tool name.
            args (dict[str, Any] | None): Arguments.

        Returns:
            tuple[str, bool]: Result text and is_error.
        """
        async with Client(self.mcp) as c:
            r = await c.call_tool(name, args or {}, raise_on_error=False)
        return r.content[0].text, bool(r.is_error)


def mock_api(responder: Responder) -> list[Recorded]:
    """Route every call to api.newscatcherapi.com through ``responder``.

    Args:
        responder (Responder): Returns ``{"status", "json", "headers"}`` for a recorded request.

    Returns:
        list[Recorded]: Requests, in order.
    """
    calls: list[Recorded] = []

    def handle(request: httpx.Request) -> httpx.Response:
        """Record and answer one request."""
        body = None
        if request.content and request.headers.get("content-type", "").startswith("application/json"):
            body = json.loads(request.content)
        rec = Recorded(
            url=str(request.url),
            method=request.method,
            body=body,
            headers=dict(request.headers),
            params=dict(request.url.params),
        )
        calls.append(rec)
        reply = responder(rec)
        return httpx.Response(reply.get("status", 200), json=reply.get("json", {}), headers=reply.get("headers", {}))

    respx.route(host="api.newscatcherapi.com").mock(side_effect=handle)
    return calls


@pytest.fixture(autouse=True)
def fast(monkeypatch: pytest.MonkeyPatch) -> None:
    """No retry back-off, no /articles pacing, a known local key."""

    async def no_sleep(_: float) -> None:
        """Skip the wait."""

    monkeypatch.setattr(client_module, "_sleep", no_sleep)
    monkeypatch.setattr(client_module._PACERS["news:/articles"], "interval_s", 0.0)
    monkeypatch.setenv("NEWSCATCHER_API_KEY", "test")
    for var in (
        "NEWSCATCHER_TOOLSETS", "NEWSCATCHER_ALLOW_KEY_IN_URL", "VERCEL_TARGET_ENV",
        "POSTHOG_PROJECT_API_KEY", "POSTHOG_ENABLED", "POSTHOG_HOST", "POSTHOG_PORT",
        "POSTHOG_APP", "POSTHOG_ENVIRONMENT", "POSTHOG_IDENTITY_SALT",
    ):
        monkeypatch.delenv(var, raising=False)
    for api in ("NEWS", "AGENT"):  # tests mock the production host
        for part in ("URL", "PORT", "ENDPOINT"):
            monkeypatch.delenv(f"NEWSCATCHER_{api}_API_{part}", raising=False)


@pytest.fixture
def setup(respx_mock: respx.MockRouter) -> Callable[..., Harness]:
    """Factory: ``setup(responder, config=None)`` → Harness."""

    def make(responder: Responder = lambda _: {}, config: Config | None = None) -> Harness:
        """Build a harness."""
        calls = mock_api(responder)
        return Harness(mcp=build_server(config or load_config()), calls=calls)

    return make
