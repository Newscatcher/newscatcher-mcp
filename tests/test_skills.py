"""Lint for the Claude Code plugin in plugin/: skill frontmatter, size, wording, tool and parameter names, manifests.

Ported from the TypeScript suite. Skills are runtime instructions tuned against model evals, so the checks guard what
breaks them: a tool or parameter the server doesn't have, banned wording, prices in currency, a malformed manifest.
"""

import json
import re
from pathlib import Path

import pytest
from fastmcp import Client

from src.config import load_config
from src.server import build_server
from tests.test_tools import BANNED

ROOT = Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "plugin"
SKILLS = sorted(p for p in (PLUGIN / "skills").iterdir() if (p / "SKILL.md").exists())
# Tools and parameters that exist only on a local server (file output). The hosted instructions tell the model they
# are missing, so skills may mention them.
LOCAL_ONLY_TOOLS = {"export_research"}
LOCAL_ONLY_PARAMS = {"save_as", "path", "csv_path"}
FRONTMATTER = re.compile(r"^---\n([\s\S]*?)\n---\n")


@pytest.fixture(scope="module")
def hosted_params() -> dict[str, set[str]]:
    """Every hosted tool's parameter names, from the server's own tool list.

    Returns:
        dict[str, set[str]]: Tool name to its input parameter names.
    """
    import asyncio

    async def go() -> dict[str, set[str]]:
        """List the tools of a fresh server."""
        async with Client(build_server(load_config())) as c:
            return {t.name: set((t.inputSchema or {}).get("properties", {}).keys()) for t in await c.list_tools()}

    return asyncio.run(go())


def test_there_are_many_skills():
    assert len(SKILLS) >= 50


@pytest.mark.parametrize("skill", SKILLS, ids=lambda p: p.name)
def test_skill_frontmatter_size_and_wording(skill: Path):
    text = (skill / "SKILL.md").read_text()
    m = FRONTMATTER.match(text)
    assert m, "frontmatter"
    fm = m.group(1)
    assert re.search(r"^name: (.+)$", fm, re.M).group(1) == skill.name
    raw = re.search(r"^description: (.+)$", fm, re.M).group(1)
    assert raw.startswith('"'), "description is a quoted YAML string"
    desc = json.loads(raw)
    assert 50 < len(desc) <= 1024
    assert len(text.splitlines()) < 500
    for b in BANNED:
        assert not re.search(b, text, re.I), f"{skill.name}: {b}"
    # keep_updated takes the schedule itself (or true), not {"schedule": …}
    assert not re.search(r'keep_updated=\{\s*"?schedule', text)


@pytest.mark.parametrize("skill", SKILLS, ids=lambda p: p.name)
def test_skill_tool_calls_use_real_tools_and_parameters(skill: Path, hosted_params: dict[str, set[str]]):
    text = (skill / "SKILL.md").read_text()
    for name in re.findall(r"`([a-z]+_[a-z_]+)\(", text):
        assert name in hosted_params or name in LOCAL_ONLY_TOOLS, f"{skill.name} uses unknown tool {name}"
    for name, args in re.findall(r"`([a-z]+_[a-z_]+)\(([^`]*)\)`", text):
        if name not in hosted_params:
            continue
        bare = re.sub(r'"(?:[^"\\]|\\.)*"', '""', args)
        bare = re.sub(r"\{[^}]*\}", "{}", bare)
        bare = re.sub(r"\[[^\]]*\]", "[]", bare)
        for param in re.findall(r"(?:^|[,(\s])([a-z_]+)\s*=", bare):
            assert param in hosted_params[name] or param in LOCAL_ONLY_PARAMS, f"{skill.name}: {name}({param}=…)"


def test_research_skills_carry_the_dry_run_and_refresh_rules():
    for skill in SKILLS:
        text = (skill / "SKILL.md").read_text()
        if "start_research(" not in text or "get_research" not in text:
            continue
        assert "dry_run=true" in text, f"{skill.name}: dry_run"
        assert "refresh" in text, f"{skill.name}: refresh hand-off"
        assert not re.search(r"\boffer (a )?(weekly )?monitor", text, re.I), f"{skill.name}: pushes a monitor"


def test_skills_that_run_the_renderer_carry_it():
    for skill in SKILLS:
        if "scripts/render-report.mjs" in (skill / "SKILL.md").read_text():
            assert (skill / "scripts" / "render-report.mjs").exists(), skill.name


def test_plugin_points_at_the_hosted_server_with_the_users_key():
    manifest = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text())
    server = manifest["mcpServers"]["newscatcher"]
    assert server["type"] == "http"
    assert server["url"].startswith("https://mcp.newscatcherapi.com/mcp")
    assert server["headers"]["x-api-key"] == "${user_config.newscatcher_api_key}"
    key = manifest["userConfig"]["newscatcher_api_key"]
    assert key["sensitive"] is True and key["required"] is True
    shared = json.loads((PLUGIN / "mcp.json").read_text())["mcpServers"]["newscatcher"]
    assert shared["url"].startswith("https://mcp.newscatcherapi.com/mcp")
    assert shared["headers"]["x-api-key"] == "${NEWSCATCHER_API_KEY}"


def test_marketplace_lists_the_plugin():
    market = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text())
    entry = next(p for p in market["plugins"] if p["name"] == "newscatcher")
    assert (ROOT / entry["source"]).joinpath(".claude-plugin", "plugin.json").exists()


def test_no_key_or_secret_in_the_plugin():
    for f in PLUGIN.rglob("*"):
        if f.is_file() and f.suffix in {".json", ".md", ".mjs"}:
            text = f.read_text(errors="ignore")
            assert not re.search(r'"x-api-key":\s*"[A-Za-z0-9]{20,}"', text), f
