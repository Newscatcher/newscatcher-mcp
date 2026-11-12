"""Sign-in with a platform account: config, the 401 challenge, discovery, registration, and token → key."""

import asyncio
import base64
import json

import httpx
import pytest
import respx
from starlette.testclient import TestClient

from src import oauth
from src.config import load_config
from src.server import create_app

from tests.conftest import mock_api
from tests.test_http import INIT, http, rpc  # noqa: F401  (http is a fixture)

PUBLIC = "https://mcp.example.com"
SUPABASE = "https://ref.supabase.co"
PLATFORM = "https://platform-api.newscatcherapi.com"
ACCOUNT = {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "get_account", "arguments": {}}}


def jwt(sub: str = "user-1", email: str = "a@example.com") -> str:
    """An unsigned JWT-shaped token (the platform API is mocked, so nothing verifies it here)."""

    def part(obj: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(obj).encode()).decode().rstrip("=")

    return f"{part({'alg': 'HS256', 'typ': 'JWT'})}.{part({'sub': sub, 'email': email, 'aud': 'authenticated'})}.sig"


@pytest.fixture
def signin_env(monkeypatch):
    """Turn sign-in on."""
    monkeypatch.setenv("NEWSCATCHER_OAUTH", "1")
    monkeypatch.setenv("NEWSCATCHER_PUBLIC_URL", PUBLIC + "/")
    monkeypatch.setenv("NEWSCATCHER_SUPABASE_URL", "ref.supabase.co")


@pytest.fixture
def signin(signin_env):
    """App with sign-in on; yields a TestClient."""
    _, app = create_app(load_config())
    with TestClient(app) as client:
        yield client


def mock_platform(orgs=None, keys=None, reveal=None, status=200):
    """Mock the platform API; returns the recorded requests."""
    calls: list[httpx.Request] = []
    orgs = orgs if orgs is not None else [
        {"organization_id": "org-personal", "organization_name": "Personal", "is_default": True},
        {"organization_id": "org-team", "organization_name": "Acme", "is_default": False},
    ]
    keys = keys if keys is not None else [
        {"api_key_id": 1, "name": "Later key", "api_key_status": "enabled", "created_at": "2026-02-01"},
        {"api_key_id": 2, "name": "Default API Key", "api_key_status": "enabled", "created_at": "2026-03-01"},
    ]

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if status != 200:
            return httpx.Response(status, json={"detail": "nope"})
        if request.url.path == "/user/organizations":
            return httpx.Response(200, json={"organizations": orgs})
        if request.url.path == "/user/api_key/list":
            return httpx.Response(200, json={"api_keys": keys})
        if request.url.path == "/user/api_key/reveal":
            body = json.loads(request.content)
            return httpx.Response(200, json=reveal if reveal is not None else {"api_key": f"key-{body['api_key_id']}"})
        return httpx.Response(404)

    respx.route(host="platform-api.newscatcherapi.com").mock(side_effect=handle)
    return calls


# --- config -------------------------------------------------------------------------------------------------


def test_sign_in_is_off_by_default():
    assert load_config().oauth is None


def test_config_normalises_the_public_url(signin_env, monkeypatch):
    monkeypatch.setenv("NEWSCATCHER_PUBLIC_URL", PUBLIC + "/mcp/")
    cfg = load_config().oauth
    assert cfg.public_url == PUBLIC and cfg.supabase_url == SUPABASE and cfg.platform_api_url == PLATFORM


@pytest.mark.parametrize(
    "var, value",
    [("NEWSCATCHER_SUPABASE_URL", ""), ("NEWSCATCHER_PUBLIC_URL", ""), ("NEWSCATCHER_PUBLIC_URL", "http://mcp.example.com"),
     ("NEWSCATCHER_SUPABASE_URL", "https://ref.supabase.co")],
)
def test_half_configured_sign_in_runs_with_keys_only(signin_env, monkeypatch, var, value):
    monkeypatch.setenv(var, value)
    assert load_config().oauth is None


# --- the 401 challenge -------------------------------------------------------------------------------------


def test_no_credentials_gets_401_naming_where_to_sign_in(signin):
    r = signin.post("/mcp", json=INIT, headers={"accept": "application/json, text/event-stream"})
    assert r.status_code == 401
    challenge = r.headers["www-authenticate"]
    assert challenge.startswith("Bearer ")
    assert f'resource_metadata="{PUBLIC}/.well-known/oauth-protected-resource/mcp"' in challenge
    assert 'scope="email profile offline_access"' in challenge


def test_without_sign_in_the_challenge_has_no_metadata(http):
    r = http.post("/mcp", json=INIT, headers={"accept": "application/json, text/event-stream"})
    assert r.status_code == 401 and "resource_metadata" not in r.headers["www-authenticate"]


def test_get_on_mcp_is_never_a_sign_in_demand(signin):
    assert signin.get("/mcp", headers={"accept": "text/event-stream"}).status_code != 401


@pytest.mark.parametrize("auth", [{"x-api-key": "user-key"}, {"authorization": "Bearer user-key"}])
def test_api_keys_still_work_with_sign_in_on(signin, respx_mock, auth):
    platform = mock_platform()
    calls = mock_api(lambda c: {"json": {"plan": "free", "credits_balance": 1}})
    status, body = rpc(signin, ACCOUNT, auth)
    assert status == 200 and not body["result"].get("isError")
    assert [c.headers["x-api-key"] for c in calls] == ["user-key"]
    assert platform == []


def test_x_api_key_wins_over_a_token(signin, respx_mock):
    platform = mock_platform()
    calls = mock_api(lambda c: {"json": {"plan": "free", "credits_balance": 1}})
    rpc(signin, ACCOUNT, {"x-api-key": "user-key", "authorization": f"Bearer {jwt()}"})
    assert [c.headers["x-api-key"] for c in calls] == ["user-key"] and platform == []


# --- token → key -------------------------------------------------------------------------------------------


def test_signed_in_caller_uses_their_workspace_default_key(signin, respx_mock):
    platform = mock_platform()
    calls = mock_api(lambda c: {"json": {"plan": "free", "credits_balance": 1}})
    token = jwt()
    assert rpc(signin, INIT, {"authorization": f"Bearer {token}"})[0] == 200
    status, body = rpc(signin, ACCOUNT, {"authorization": f"Bearer {token}"})
    assert status == 200 and not body["result"].get("isError")
    assert [c.headers["x-api-key"] for c in calls] == ["key-2"]  # "Default API Key", not the oldest
    # Looked up once (cached for the second request), with the user's token, in the non-Personal workspace.
    assert [r.url.path for r in platform] == ["/user/organizations", "/user/api_key/list", "/user/api_key/reveal"]
    assert all(r.headers["authorization"] == f"Bearer {token}" for r in platform)
    assert "x-organization-id" not in platform[0].headers
    assert platform[1].headers["x-organization-id"] == "org-team"
    assert platform[0].headers["x-user-email"] == "a@example.com"


def test_rejected_token_gets_401_invalid_token(signin, respx_mock):
    mock_platform(status=401)
    status, _ = rpc(signin, INIT, {"authorization": f"Bearer {jwt()}"})
    r = signin.post("/mcp", json=INIT, headers={"accept": "application/json, text/event-stream", "authorization": f"Bearer {jwt()}"})
    assert status == 401 and r.status_code == 401
    assert 'error="invalid_token"' in r.headers["www-authenticate"]
    assert "resource_metadata=" in r.headers["www-authenticate"]


def test_account_without_workspace_connects_and_tools_say_what_to_do(signin, respx_mock):
    mock_platform(orgs=[])
    calls = mock_api(lambda c: {"json": {}})
    token = jwt()
    assert rpc(signin, INIT, {"authorization": f"Bearer {token}"})[0] == 200
    status, body = rpc(signin, ACCOUNT, {"authorization": f"Bearer {token}"})
    assert status == 200 and body["result"]["isError"]
    assert "not set up yet" in body["result"]["content"][0]["text"]
    assert calls == []  # the token is never sent upstream as a key


def test_platform_outage_is_not_cached(signin, respx_mock):
    mock_platform(status=503)
    token = jwt()
    _, body = rpc(signin, ACCOUNT, {"authorization": f"Bearer {token}"})
    assert body["result"]["isError"] and "Try again" in body["result"]["content"][0]["text"]
    assert oauth._keys == {}


def test_a_token_is_only_a_key_when_sign_in_is_off(http, respx_mock):
    calls = mock_api(lambda c: {"json": {"plan": "free", "credits_balance": 1}})
    token = jwt()
    rpc(http, ACCOUNT, {"authorization": f"Bearer {token}"})
    assert [c.headers["x-api-key"] for c in calls] == [token]  # unchanged behaviour without sign-in


def test_concurrent_requests_share_one_lookup(signin_env, respx_mock):
    platform = mock_platform()
    cfg = load_config().oauth
    token = jwt()

    async def both():
        return await asyncio.gather(oauth.key_for_token(cfg, token), oauth.key_for_token(cfg, token))

    assert asyncio.run(both()) == ["key-2", "key-2"]
    assert len(platform) == 3


def test_reveal_rate_limit_is_waited_out_once(signin_env, respx_mock):
    replies = iter([httpx.Response(429), httpx.Response(200, json={"api_key": "k"})])
    respx.get(f"{PLATFORM}/user/organizations").respond(200, json={"organizations": [{"organization_id": "o"}]})
    respx.get(f"{PLATFORM}/user/api_key/list").respond(
        200, json={"api_keys": [{"api_key_id": 1, "api_key_status": "enabled", "created_at": "x"}]}
    )
    respx.post(f"{PLATFORM}/user/api_key/reveal").mock(side_effect=lambda _: next(replies))
    assert asyncio.run(oauth.key_for_token(load_config().oauth, jwt())) == "k"


def test_pickers_mirror_the_platform_app():
    assert oauth.pick_workspace([{"organization_id": "p", "organization_name": "Personal", "is_default": True}])["organization_id"] == "p"
    assert oauth.pick_workspace([]) is None
    assert oauth.pick_default_key([{"api_key_id": 1, "api_key_status": "disabled", "name": "Default API Key"}]) is None
    oldest = oauth.pick_default_key(
        [{"api_key_id": 1, "api_key_status": "enabled", "created_at": "2026-05-01"},
         {"api_key_id": 2, "api_key_status": "enabled", "created_at": "2026-01-01"}]
    )
    assert oldest["api_key_id"] == 2


def test_jwt_shape():
    assert oauth.looks_like_jwt(jwt())
    assert not oauth.looks_like_jwt("ncsk_abc123")
    assert not oauth.looks_like_jwt("eyJ.only-two")


# --- discovery and registration ----------------------------------------------------------------------------


@pytest.mark.parametrize("path", ["/.well-known/oauth-protected-resource/mcp", "/.well-known/oauth-protected-resource"])
def test_protected_resource_names_this_server(signin, path):
    doc = signin.get(path).json()
    assert doc["resource"] == f"{PUBLIC}/mcp" and doc["authorization_servers"] == [PUBLIC]
    assert "openid" not in doc["scopes_supported"] and "offline_access" in doc["scopes_supported"]


@pytest.mark.parametrize("path", ["/.well-known/oauth-authorization-server", "/.well-known/openid-configuration"])
def test_authorization_server_metadata_points_registration_here(signin, respx_mock, path):
    respx.get(f"{SUPABASE}/auth/v1/.well-known/oauth-authorization-server").respond(
        200,
        json={"issuer": f"{SUPABASE}/auth/v1", "authorization_endpoint": f"{SUPABASE}/auth/v1/oauth/authorize",
              "token_endpoint": f"{SUPABASE}/auth/v1/oauth/token", "registration_endpoint": f"{SUPABASE}/auth/v1/oauth/clients/register",
              "scopes_supported": ["openid", "profile", "email", "phone", "offline_access"]},
    )
    doc = signin.get(path).json()
    assert doc["issuer"] == PUBLIC and doc["registration_endpoint"] == f"{PUBLIC}/oauth/register"
    assert doc["authorization_endpoint"].startswith(SUPABASE) and doc["token_endpoint"].startswith(SUPABASE)
    # No `openid`: an HS256 auth project cannot sign the ID token it implies, and the token request fails.
    assert "openid" not in doc["scopes_supported"]


def test_metadata_outage_is_a_502(signin, respx_mock):
    respx.get(f"{SUPABASE}/auth/v1/.well-known/oauth-authorization-server").respond(500)
    assert signin.get("/.well-known/oauth-authorization-server").status_code == 502


@pytest.mark.parametrize(("sent", "forwarded"), [(None, "none"), ("client_secret_post", "client_secret_post")])
def test_registration_makes_silent_clients_public(signin, respx_mock, sent, forwarded):
    route = respx.post(f"{SUPABASE}/auth/v1/oauth/clients/register").respond(201, json={"client_id": "c"})
    body = {"client_name": "Claude", "redirect_uris": ["https://claude.ai/cb"]}
    if sent:
        body["token_endpoint_auth_method"] = sent
    r = signin.post("/oauth/register", json=body)
    assert r.status_code == 201 and r.json() == {"client_id": "c"}
    assert json.loads(route.calls[0].request.content)["token_endpoint_auth_method"] == forwarded


def test_registration_rejects_non_objects(signin):
    assert signin.post("/oauth/register", content=b"[1]", headers={"content-type": "application/json"}).status_code == 400


def test_root_names_the_mcp_endpoint(signin):
    assert signin.get("/").json()["mcp_endpoint"] == f"{PUBLIC}/mcp"


def test_no_sign_in_routes_without_sign_in(http):
    assert http.get("/.well-known/oauth-protected-resource").status_code == 404
