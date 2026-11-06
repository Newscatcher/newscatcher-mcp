"""The hosted HTTP app: keys per request, no server-side key fallback, toolsets per connection, health."""

import json

import pytest
from starlette.testclient import TestClient

from src.config import load_config
from src.server import create_app

from tests.conftest import mock_api

INIT = {
    "jsonrpc": "2.0", "id": 1, "method": "initialize",
    "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "pytest", "version": "1"}},
}
HEADERS = {"accept": "application/json, text/event-stream", "content-type": "application/json"}


def rpc(client: TestClient, payload: dict, headers: dict | None = None, path: str = "/mcp") -> tuple[int, dict | None]:
    """POST one JSON-RPC message and decode the (JSON or SSE) answer."""
    r = client.post(path, json=payload, headers={**HEADERS, **(headers or {})})
    if r.status_code != 200:
        return r.status_code, r.json() if r.headers.get("content-type", "").startswith("application/json") else None
    if r.headers.get("content-type", "").startswith("text/event-stream"):
        data = [line[5:].strip() for line in r.text.splitlines() if line.startswith("data:")]
        return 200, json.loads(data[-1])
    return 200, r.json()


@pytest.fixture
def http():
    """Fresh app per test; yields a TestClient."""
    _, app = create_app(load_config())
    with TestClient(app) as client:
        yield client


def test_health(http):
    r = http.get("/health")
    assert r.status_code == 200 and r.json()["ok"] is True


def test_post_without_key_gets_401_with_www_authenticate(http):
    r = http.post("/mcp", json=INIT, headers=HEADERS)
    assert r.status_code == 401
    assert r.headers["www-authenticate"].startswith("Bearer")
    assert "x-api-key" in r.json()["error"]


def test_body_over_1_mib_is_refused(http):
    r = http.post("/mcp", content=b"x" * 1_048_577, headers={**HEADERS, "x-api-key": "k"})
    assert r.status_code == 413


def test_key_in_url_only_when_opted_in(monkeypatch):
    _, app = create_app(load_config())
    with TestClient(app) as c:
        assert rpc(c, INIT, path="/mcp?apiKey=k")[0] == 401
    monkeypatch.setenv("NEWSCATCHER_ALLOW_KEY_IN_URL", "1")
    _, app = create_app(load_config())
    with TestClient(app) as c:
        assert rpc(c, INIT, path="/mcp?apiKey=k")[0] == 200


@pytest.mark.parametrize("auth", [{"x-api-key": "user-key"}, {"authorization": "Bearer user-key"}])
def test_callers_key_is_forwarded_and_server_key_never_used(http, respx_mock, auth):
    # NEWSCATCHER_API_KEY=test is set on the server (conftest): over HTTP it must be ignored.
    calls = mock_api(lambda c: {"json": {"plan": "free", "credits_balance": 1}})
    status, body = rpc(http, {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "get_account", "arguments": {}}}, auth)
    assert status == 200 and not body["result"].get("isError")
    assert [c.headers["x-api-key"] for c in calls] == ["user-key"]


def test_tools_query_param_picks_toolsets(http):
    _, body = rpc(http, {"jsonrpc": "2.0", "id": 3, "method": "tools/list"}, {"x-api-key": "k"}, path="/mcp?tools=news")
    assert [t["name"] for t in body["result"]["tools"]] == ["search_news", "list_articles", "count_articles", "get_story", "get_account"]
    _, body = rpc(http, {"jsonrpc": "2.0", "id": 4, "method": "tools/list"}, {"x-api-key": "k"})
    assert len(body["result"]["tools"]) == 15


def test_client_query_param_tags_user_agent(http, respx_mock):
    calls = mock_api(lambda c: {"json": {"plan": "free"}})
    rpc(http, {"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "get_account", "arguments": {}}},
        {"x-api-key": "k"}, path="/mcp?client=cursor")
    assert calls[0].headers["user-agent"].endswith("(cursor)")
