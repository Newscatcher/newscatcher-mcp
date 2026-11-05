"""PostHog settings (same env vars as agent-service) and the rule that analytics never changes the tool contract."""

import json

from src.analytics import _identity_digest, init_analytics, posthog_settings
from src.config import load_config
from src.server import build_server


def test_defaults():
    s = posthog_settings()
    assert s["enabled"] is True
    assert s["host_url"] == "https://us.i.posthog.com"
    assert s["app"] == "newscatcher-mcp"
    assert s["environment"] == "local"


def test_overrides_and_vercel_fallback(monkeypatch):
    monkeypatch.setenv("POSTHOG_HOST", "https://eu.i.posthog.com/")
    monkeypatch.setenv("POSTHOG_PORT", "8443")
    monkeypatch.setenv("POSTHOG_APP", "mcp")
    monkeypatch.setenv("VERCEL_TARGET_ENV", "preview")
    s = posthog_settings()
    assert s["host_url"] == "https://eu.i.posthog.com:8443"
    assert s["app"] == "mcp" and s["environment"] == "preview"
    monkeypatch.setenv("POSTHOG_ENVIRONMENT", "dev")
    assert posthog_settings()["environment"] == "dev"


def test_disabled_flag_wins_over_key(monkeypatch):
    monkeypatch.setenv("POSTHOG_PROJECT_API_KEY", "phc_test")
    monkeypatch.setenv("POSTHOG_ENABLED", "false")
    assert init_analytics(build_server(load_config()), load_config()) is None


def test_off_without_key():
    assert init_analytics(build_server(load_config()), load_config()) is None


async def test_enabled_tags_every_event_and_keeps_tool_contract(monkeypatch):
    plain = build_server(load_config())
    before = {t.name: json.dumps(t.parameters, sort_keys=True) for t in await plain.list_tools()}

    monkeypatch.setenv("POSTHOG_PROJECT_API_KEY", "phc_test")
    monkeypatch.setenv("POSTHOG_ENVIRONMENT", "production")
    instrumented = build_server(load_config())
    client = init_analytics(instrumented, load_config())
    try:
        assert client is not None
        assert client.super_properties == {"app": "newscatcher-mcp", "environment": "production"}
        after = {t.name: json.dumps(t.parameters, sort_keys=True) for t in await instrumented.list_tools()}
        assert after == before
    finally:
        client.disabled = True
        client.shutdown()


def test_identity_is_a_keyed_hash_not_the_key():
    digest = _identity_digest("sk-user-key", "salt")
    assert digest.startswith("key_") and "sk-user-key" not in digest
    assert digest == _identity_digest("sk-user-key", "salt") != _identity_digest("sk-user-key", "other-salt")
