"""Tool behaviour: parameter mapping, rendering, errors, retries, time budget, lenient input."""

import asyncio
import dataclasses
import json
import re
import time

import pytest
from fastmcp import Client
from pydantic import TypeAdapter

from src import client as client_module
from src.client import NewsCatcherClient
from src.config import load_config
from src.guides import GUIDES
from src.server import INSTRUCTIONS, build_server
from src.tools.research import MaxRows, query_tips

BANNED = [
    r"\$\s?\d", r"\bdollars?\b", r"every page read", r"reads? (the|every) articles?", r"whole article", r"full[- ]text", r"full content",
    r"article text", r"\bcontent field\b", r"robots", r"\bv4\b", r"instead of (your )?built-in",
]
TOOLS = [
    "search_news", "list_articles", "count_articles", "get_story", "get_account",
    "start_research", "get_research", "cancel_research", "resend_results",
    "save_company_list", "get_company_list", "edit_company_list",
    "create_monitor", "get_monitor", "get_monitor_updates", "update_monitor",
]


async def list_tools(mcp):
    async with Client(mcp) as c:
        return await c.list_tools()


# ---------------------------------------------------------------- tool surface


async def test_registers_the_16_hosted_tools():
    tools = await list_tools(build_server(load_config()))
    assert [t.name for t in tools] == TOOLS


async def test_descriptions_short_and_free_of_banned_wording():
    for t in await list_tools(build_server(load_config())):
        assert len(t.description) <= 2048, t.name
        schema = json.dumps(t.input_schema)
        for b in BANNED:
            assert not re.search(b, t.description, re.I), (t.name, b)
            assert not re.search(b, schema, re.I), (t.name, b)
        # Local-file features are not offered by the hosted server, so nothing may point at them.
        for word in (r"\bexport_research\b", r"\bsave_as\b", r"\bcsv_path\b"):
            assert not re.search(word, t.description + schema), (t.name, word)


def test_instructions_under_listing_limit_and_clean():
    assert len(INSTRUCTIONS) < 4096
    for b in BANNED:
        assert not re.search(b, INSTRUCTIONS, re.I)
        for g in GUIDES.values():
            assert not re.search(b, g["text"], re.I), g["title"]


async def test_annotations():
    tools = {t.name: t for t in await list_tools(build_server(load_config()))}
    assert tools["search_news"].annotations.read_only_hint is True
    assert tools["start_research"].annotations.read_only_hint is False
    assert tools["update_monitor"].annotations.destructive_hint is True
    assert tools["edit_company_list"].annotations.destructive_hint is True
    assert tools["search_news"].meta["anthropic/alwaysLoad"] is True


async def test_honours_toolsets_env(monkeypatch):
    monkeypatch.setenv("NEWSCATCHER_TOOLSETS", "news")
    mcp = build_server(load_config())
    assert [t.name for t in await list_tools(mcp)] == TOOLS[:5]
    async with Client(mcp) as c:
        r = await c.call_tool("start_research", {"query": "x"}, raise_on_error=False)
    assert r.is_error and "not enabled on this connection" in r.content[0].text


async def test_schemas_optional_and_described_after_lenient_wrappers():
    tools = {t.name: t for t in await list_tools(build_server(load_config()))}
    js = tools["start_research"].input_schema
    assert "companies" not in js.get("required", [])
    assert "Research these companies" in js["properties"]["companies"]["description"]
    assert js["properties"]["dry_run"]["type"] == "boolean"
    assert "from" in tools["count_articles"].input_schema["required"]


# ---------------------------------------------------------------- parameter mapping


async def test_search_news_maps_friendly_params(setup):
    h = setup(lambda c: {"json": {"query": "x", "effort": "low", "window": {"search_window": "2h"}, "count": 0, "results": []}})
    await h.call(
        "search_news",
        {"query": "Tesla NOT Musk", "window": "2h", "effort": "low", "group": "story", "sort": "newest",
         "exclude_sources": ["a.com"], "languages": ["de"], "include_non_news": True},
    )
    c = h.calls[0]
    assert c.url.endswith("/news-api/search")
    assert c.body == {
        "q": "Tesla NOT Musk", "search_window": "2h", "effort": "low", "collapse": "story", "sort_by": "published_at",
        "not_sources": ["a.com"], "languages": ["de"], "content_type": "all", "limit": 10,
    }
    assert c.headers["x-api-key"] == "test"
    assert c.headers["user-agent"].startswith("newscatcher-mcp/")


async def test_list_articles_count_only(setup):
    h = setup(lambda c: {"json": {"query": "q", "total_hits": 1234, "window": {"from": "2026-10-01T00:00:00Z", "to": "2026-11-01T00:00:00Z"}, "results": [{"title": "t"}]}})
    text, _ = await h.call("list_articles", {"query": "q", "count_only": True, "sort": "oldest"})
    assert h.calls[0].body["page_size"] == 1 and h.calls[0].body["page"] == 1 and h.calls[0].body["sort_by"] == "-published_at"
    assert "1,234 matching articles (exact)" in text


async def test_list_articles_paging_hint_pins_window_end(setup):
    h = setup(lambda c: {"json": {"query": "q", "total_hits": 50, "total_pages": 3, "page": 1, "page_size": 20, "window": {"from": "a", "to": "2026-11-01T00:00:00Z"}, "results": [{"title": "t", "url": "u", "source": {"name": "S"}}]}})
    text, _ = await h.call("list_articles", {"query": "q"})
    assert 'page=2 and to="2026-11-01T00:00:00Z"' in text


async def test_start_research_bodies(setup):
    h = setup(lambda c: {"status": 202, "json": {"run_id": "r1", "status": "queued", "kind": "events"}})
    await h.call("start_research", {"query": "Bank M&A since Oct 1", "mode": "standard", "keep_updated": True})
    assert h.calls[0].body == {"query": "Bank M&A since Oct 1", "mode": "standard", "keep_updated": {}}
    await h.call("start_research", {"companies": ["stripe.com", {"domain": "wise.com", "name": "Wise"}], "query": "funding", "lookback_days": 14})
    b = h.calls[1].body
    assert b["query"] == "funding" and b["lookback_days"] == 14
    assert b["companies"]["items"] == [{"domain": "stripe.com"}, {"domain": "wise.com", "name": "Wise"}]
    assert "mode" not in b


async def test_start_research_refuses_empty_request(setup):
    h = setup()
    text, err = await h.call("start_research", {})
    assert err and "Give a query" in text
    assert not h.calls


async def test_create_monitor_dataset_kind(setup):
    h = setup(lambda c: {"json": {"status": "succeeded", "kind": "events"}} if "/runs/" in c.url else {"status": 201, "json": {"monitor_id": "m1", "name": "n", "kind": "dataset", "enabled": True, "schedule": {"every": "week", "at": "09:00", "tz": "UTC", "weekday": 2}}})
    text, _ = await h.call("create_monitor", {"from_run_id": "r1"})
    assert h.calls[1].body["kind"] == "dataset" and h.calls[1].body["from_run_id"] == "r1"
    assert "weekly on Wed" in text


async def test_weekly_schedule_defaults_to_monday(setup):
    h = setup(lambda c: {"json": {"status": "succeeded", "kind": "events"}} if "/runs/" in c.url else {"status": 201, "json": {"monitor_id": "m", "kind": "dataset", "schedule": {"every": "week", "weekday": 0, "at": "09:00", "tz": "UTC"}}})
    await h.call("create_monitor", {"from_run_id": "r", "schedule": {"every": "week"}})
    assert h.calls[1].body["schedule"]["weekday"] == 0


# ---------------------------------------------------------------- tally


async def test_tally_by_outlet_and_person_bylines(setup):
    h = setup(lambda c: {"json": {"query": "q", "total_hits": 3, "total_pages": 1, "page": 1, "page_size": 100, "window": {"from": "a", "to": "b"}, "results": [
        {"title": "t1", "url": "u1", "published_at": "2026-11-02T00:00:00Z", "source": {"domain": "a.com"}, "author": "Jane Roe"},
        {"title": "t2", "url": "u2", "published_at": "2026-11-03T00:00:00Z", "source": {"domain": "a.com"}, "author": "Staff"},
        {"title": "t3", "url": "u3", "published_at": "2026-11-01T00:00:00Z", "source": {"domain": "b.com"}, "author": "John Doe"},
    ]}})
    by_source, _ = await h.call("list_articles", {"query": "q", "tally": "source"})
    assert re.search(r"1\. a\.com · 2 \(67%\)[\s\S]*latest 2026-11-03", by_source)
    by_author, _ = await h.call("list_articles", {"query": "q", "tally": "author"})
    assert "Jane Roe" in by_author and "Staff" not in by_author


async def test_tally_several_fields_in_one_pass(setup):
    h = setup(lambda c: {"json": {"query": "q", "total_hits": 2, "total_pages": 1, "window": {"from": "a", "to": "b"}, "results": [
        {"title": "t1", "url": "u1", "published_at": "2026-11-02T00:00:00Z", "source": {"domain": "a.com"}, "country": "US", "language": "en"},
        {"title": "t2", "url": "u2", "published_at": "2026-11-03T00:00:00Z", "source": {"domain": "b.de"}, "country": "DE", "language": "de"},
    ]}})
    text, _ = await h.call("list_articles", {"query": "q", "tally": '["source","country","language"]'})
    assert len(h.calls) == 1
    for s in ("By source: 2 distinct values", "By country: 2 distinct values", "By language: 2 distinct values", "(all of them)"):
        assert s in text


async def test_tally_pages_with_pinned_window_end(setup):
    def reply(c):
        page = c.body["page"]
        return {"json": {"query": "q", "total_hits": 150, "total_pages": 2, "page": page, "window": {"from": "2026-11-01T00:00:00Z", "to": "2026-11-04T00:00:00Z"},
                         "results": [{"title": f"t{i}", "url": f"u{i}", "published_at": "2026-11-02T00:00:00Z", "source": {"domain": "s.com"}} for i in range(100 if page == 1 else 50)]}}
    h = setup(reply)
    text, _ = await h.call("list_articles", {"query": "q", "tally": "source", "tally_pages": 2})
    assert [c.body["page"] for c in h.calls] == [1, 2]
    assert h.calls[1].body["to_date"] == "2026-11-04T00:00:00Z"
    assert "tallied the 150 newest" in text


# ---------------------------------------------------------------- company lists


async def test_saves_a_list_from_a_company_run(setup):
    h = setup(lambda c: {"status": 201, "json": {"list_id": "l1", "name": "n", "count": 2, "status": "ready", "companies": []}})
    await h.call("save_company_list", {"from_run_id": "r1", "name": "Accounts"})
    assert "/companies/lists/from-run/r1" in h.calls[0].url
    assert h.calls[0].body == {"name": "Accounts"}


async def test_needs_exactly_one_source_of_companies(setup):
    h = setup()
    _, err = await h.call("save_company_list", {"from_run_id": "r1", "companies": ["a.com"]})
    assert err


# ---------------------------------------------------------------- monitor updates


async def test_skips_source_run_while_first_monitor_run_pending(setup):
    h = setup(lambda c: {"json": {"runs": [{"run_id": "m1", "role": "scheduled", "status": "running"}, {"run_id": "src", "role": "source", "status": "succeeded"}]}}
              if c.url.split("?")[0].endswith("/runs") else {"json": {"monitor_id": "x", "enabled": True, "next_run_at": "2026-11-05T09:00:00Z"}})
    text, _ = await h.call("get_monitor_updates", {"monitor_id": "x"})
    assert "m1 is running" in text
    assert 'get_research(run_id="src")' in text


async def test_renders_company_monitor_stories(setup):
    h = setup(lambda c: {"json": {"run_id": "m1", "status": "succeeded", "stories": [{"company": "notion.so", "update": False, "story": {"headline": "Notion launches agents", "summary": "s", "story_type": "product", "importance": 4, "outlets": 14, "last_date": "2026-11-04", "lead": {"url": "https://x"}}}]}}
              if "/monitors/runs/" in c.url else {"json": {"runs": [{"run_id": "m1", "role": "scheduled", "status": "succeeded"}]}})
    text, _ = await h.call("get_monitor_updates", {"monitor_id": "x"})
    assert "[new] 2026-11-04 · notion.so · product" in text
    assert "Notion launches agents" in text


async def test_dataset_monitor_feed_reads_rows(setup):
    h = setup(lambda c: {"json": {"rows": [{"change": "new", "company": "A", "source_url": "u"}]}} if "/rows" in c.url else {"json": {"kind": "dataset"}})
    text, _ = await h.call("get_monitor_updates", {"monitor_id": "x", "feed": True})
    assert any("/monitors/x/rows" in c.url for c in h.calls)
    assert "| change | company | source_url |" in text


# ---------------------------------------------------------------- errors and retries


async def test_retries_429_then_succeeds(setup):
    n = {"i": 0}

    def reply(c):
        n["i"] += 1
        return {"status": 429, "json": {"message": "slow down"}, "headers": {"retry-after": "1"}} if n["i"] == 1 else {"json": {"ok": True}}

    calls = setup(reply).calls
    async with NewsCatcherClient(load_config(), "k") as client:
        assert await client.get("news", "/subscription") == {"ok": True}
    assert len(calls) == 2


async def test_never_retries_run_start_after_5xx_but_retries_searches(setup):
    h = setup(lambda c: {"status": 503, "json": {"message": "upstream"}})
    text, err = await h.call("start_research", {"query": "x"})
    assert len(h.calls) == 1 and err
    assert "may have gone through" in text
    h.calls.clear()
    await h.call("search_news", {"query": "x"})
    assert len(h.calls) == 3


def test_rounds_max_rows_up_to_an_allowed_size():
    ta = TypeAdapter(MaxRows)
    assert ta.validate_python(75) == 100
    # A run asks for 100 rows at most (the plan's rows per run): more is capped, not refused.
    assert ta.validate_python(150) == 100
    assert ta.validate_python(500) == 100
    assert ta.validate_python(None) is None


async def test_api_errors_become_actionable(setup):
    h = setup(lambda c: {"status": 403, "json": {"message": "Your plan allows up to 50 results per request", "status_code": 403}, "headers": {"correlation-id": "cid-1"}})
    text, err = await h.call("search_news", {"query": "x", "limit": 100})
    assert err
    assert re.search(r"403.*50 results.*cid-1.*Lower the limit", text, re.S)


async def test_explains_archive_outages(setup):
    h = setup(lambda c: {"status": 503, "json": {"message": "The news search backend is not available."}})
    text, _ = await h.call("list_articles", {"query": "x", "from": "2026-01-01", "count_only": True})
    assert "Retrying the same window will fail again" in text


async def test_count_keeps_buckets_the_outage_misses(setup):
    h = setup(lambda c: {"json": {"total_hits": 7}} if c.body["from_date"].startswith("2026-11-01") else {"status": 503, "json": {"message": "The news search backend is not available."}})
    text, err = await h.call("count_articles", {"queries": ["x"], "from": "2026-10-31", "to": "2026-11-01", "interval": "day"})
    assert not err
    assert "| 2026-10-31 | n/a |" in text and "| 2026-11-01 | 7 |" in text
    assert "Retry in a moment" not in text


async def test_fixes_model_mistakes_before_they_cost_a_call(setup):
    h = setup(lambda c: {"json": {"effort": "medium", "count": 0, "results": [], "window": {}}})
    text, _ = await h.call("search_news", {"query": "x", "window": "90d"})
    assert h.calls[0].body["search_window"] == "30d"
    assert 'Window "90d" cut to the last 30 days' in text
    h.calls.clear()
    bad, err = await h.call("list_articles", {"query": '"climate tech" AND fintech OR "green fintech"'})
    assert err and "can't be mixed" in bad and bad.startswith("Invalid arguments: query:")
    assert not h.calls
    _, err = await h.call("list_articles", {"query": '("climate tech" AND fintech) OR ("green fintech" NOT "x OR y")', "search_in": "title", "languages": "en,de"})
    assert not err
    assert h.calls[0].body["search_in"] == ["title"] and h.calls[0].body["languages"] == ["en", "de"]
    bad, err = await h.call("list_articles", {"query": "site:reuters.com"})
    assert err and "Remove the characters" in bad


async def test_top_sources_normalised_and_checked(setup):
    h = setup(lambda c: {"json": {"query": "q", "total_hits": 0, "results": []}})
    await h.call("list_articles", {"query": "q", "top_sources": "top 200"})
    assert h.calls[0].body["predefined_sources"] == "top 200 global"
    text, err = await h.call("list_articles", {"query": "q", "top_sources": "best ones"})
    assert err and "top <n>" in text


async def test_count_moves_start_older_than_12_months(setup):
    h = setup(lambda c: {"json": {"total_hits": 1}})
    text, _ = await h.call("count_articles", {"queries": ["x"], "from": "2020-01-01", "interval": "month"})
    assert "Start moved to" in text
    assert len(h.calls) <= 13


async def test_needs_a_key(setup, monkeypatch):
    monkeypatch.delenv("NEWSCATCHER_API_KEY")
    h = setup()
    text, err = await h.call("get_account")
    assert err and "401" in text and "x-api-key" in text
    assert not h.calls


async def test_spaces_articles_calls_about_a_second_apart(setup, monkeypatch):
    monkeypatch.setattr(client_module._PACERS["news:/articles"], "interval_s", 1.05)
    times: list[float] = []
    setup(lambda c: (times.append(time.monotonic()), {"json": {}})[1])
    async with NewsCatcherClient(load_config(), "k") as client:
        await asyncio.gather(client.post("news", "/articles", {}), client.post("news", "/articles", {}))
    assert times[1] - times[0] >= 1.0


async def test_invalid_arguments_are_short_and_name_the_field(setup):
    h = setup()
    text, err = await h.call("search_news", {"query": "x", "effort": "extreme"})
    assert err and text.startswith("Invalid arguments: effort:")
    assert "pydantic.dev" not in text


async def test_unexpected_errors_hide_internals_and_give_a_tracking_id(setup):
    h = setup(lambda c: {"json": ["not", "an", "object"]})
    text, err = await h.call("get_account")
    assert err and "tracking id" in text and "Traceback" not in text


# ---------------------------------------------------------------- time budget (hosted)


async def test_count_answers_with_partial_timeline_when_time_runs_out(setup):
    cfg = dataclasses.replace(load_config(), max_call_seconds=1)  # less than the wrap-up margin: nothing fits
    h = setup(lambda c: {"json": {"total_hits": 5}}, config=cfg)
    text, err = await h.call("count_articles", {"queries": ["x"], "from": "2026-10-01", "to": "2026-10-03"})
    assert not err
    assert "time limit for one call ran out" in text
    assert not h.calls


async def test_get_research_wait_is_capped_by_time_budget(setup):
    cfg = dataclasses.replace(load_config(), max_call_seconds=1)
    h = setup(lambda c: {"json": {"run_id": "r", "status": "running", "mode": "fast"}}, config=cfg)
    started = time.monotonic()
    text, _ = await h.call("get_research", {"run_id": "r", "wait_seconds": 300})
    assert time.monotonic() - started < 5
    assert len(h.calls) == 1
    assert 'say "refresh"' in text


# ---------------------------------------------------------------- borrowed from the CatchAll MCP


async def test_accepts_lists_and_objects_as_json_text(setup):
    h = setup(lambda c: {"status": 202, "json": {"run_id": "r1", "status": "queued", "kind": "companies"}})
    await h.call("start_research", {"companies": '["stripe.com", {"domain":"wise.com","name":"Wise"}]', "keep_updated": '{"every":"week"}'})
    assert h.calls[0].body["companies"]["items"] == [{"domain": "stripe.com"}, {"domain": "wise.com", "name": "Wise"}]
    assert h.calls[0].body["keep_updated"]["schedule"]["every"] == "week"
    assert h.calls[0].body["keep_updated"]["schedule"]["weekday"] == 0
    await h.call("start_research", {"query": "Bank M&A since Oct 1, 2026", "keep_updated": "true"})
    assert h.calls[1].body["keep_updated"] == {}


async def test_queries_with_commas_stay_one_query(setup):
    h = setup(lambda c: {"json": {"total_hits": 1}})
    # to="2026-10-01" is the end of that day: one daily bucket, so one call per query.
    text, _ = await h.call("count_articles", {"queries": '"Tesla, Inc."', "from": "2026-10-01", "to": "2026-10-01"})
    assert len(h.calls) == 1 and h.calls[0].body["q"] == '"Tesla, Inc."'
    h.calls.clear()
    await h.call("count_articles", {"queries": '["Tesla", "Rivian"]', "from": "2026-10-01", "to": "2026-10-01"})
    assert [c.body["q"] for c in h.calls] == ["Tesla", "Rivian"]


async def test_edit_list_accepts_comma_string(setup):
    h = setup(lambda c: {"json": {"list_id": "l", "name": "n", "count": 0, "status": "ready", "companies": []}})
    await h.call("edit_company_list", {"list_id": "l", "remove": "a.com,b.com"})
    assert [c.url.rsplit("/", 1)[1] for c in h.calls if c.method == "DELETE"] == ["a.com", "b.com"]


async def test_explicit_null_is_accepted_for_optional_lists(setup):
    h = setup(lambda c: {"json": {"effort": "medium", "count": 0, "results": [], "window": {}}})
    _, err = await h.call("search_news", {"query": "x", "languages": None, "sources": None})
    assert not err


async def test_dry_run_starts_nothing_and_shows_cost_balance_and_tips(setup):
    h = setup(lambda c: {"json": {"credits_balance": 2500}} if "/subscription" in c.url else {"status": 500})
    text, _ = await h.call("start_research", {"query": "news articles about tech layoffs", "mode": "standard", "max_rows": 100, "dry_run": True})
    assert all(c.method == "GET" for c in h.calls)
    for s in ("nothing was started or charged", "Standard runs take 10–30 minutes", "at most 4,500 credits.",
              "Balance: 2,500 credits (not enough", "No time window", "Describe the events, not the coverage"):
        assert s in text
    assert "$" not in text


async def test_dry_run_counts_saved_list_and_prices_the_monitor(setup):
    h = setup(lambda c: {"json": {"list_id": "l1", "count": 60}} if "/companies/lists/" in c.url else {"json": {"credits_balance": 1_000_000}})
    text, _ = await h.call("start_research", {"company_list_id": "l1", "keep_updated": True, "dry_run": True})
    for s in ("company news for 60 companies", "run as a batch", "30,000 credits for 60 companies",
              "180,000 credits a month", "Query check: no issues found", "about 1–2 hours for 60 companies",
              "3 companies at a time per account", "does not make them faster"):
        assert s in text
    assert "$" not in text


async def test_dry_run_of_many_typed_companies_runs_in_parts(setup):
    h = setup(lambda c: {"json": {"credits_balance": 1_000_000}})
    domains = [f"c{i}.com" for i in range(60)]
    text, _ = await h.call("start_research", {"companies": domains, "dry_run": True})
    assert "runs in parts of 50 companies" in text
    assert "run as a batch" not in text


def test_query_tips():
    assert query_tips("Product recalls announced by US auto makers since September 1, 2026, with model and reason", "events") == []
    assert len(query_tips("layoffs", "events")) == 2
    assert query_tips("funding, acquisitions and leadership changes", "companies") == []


async def test_get_research_numbers_rows(setup):
    detail = {"run_id": "r1", "status": "succeeded", "kind": "events", "columns": ["company", "date"],
              "rows": [{"company": "A", "date": "2026-10-01"}, {"company": "A", "date": "2026-10-01"}, {"company": "B", "date": "2026-10-02"}]}
    h = setup(lambda c: {"json": detail})
    text, _ = await h.call("get_research", {"run_id": "r1", "wait_seconds": 0})
    assert "| # | company | date |" in text
    assert "| 2 | A | 2026-10-01 |" in text


async def test_get_research_leaves_out_rows_and_recounts_by_importance(setup):
    detail = {"run_id": "r1", "status": "succeeded", "kind": "companies", "columns": ["company", "story_type", "importance", "date"],
              "rows": [{"company": "A", "story_type": "funding", "importance": 2, "date": "2026-10-01"},
                       {"company": "A", "story_type": "funding", "importance": 4, "date": "2026-10-03"},
                       {"company": "B", "story_type": "layoffs", "importance": 3, "date": "2026-10-02"},
                       {"company": "B", "story_type": "funding", "importance": 3, "date": "2026-10-05"}]}
    h = setup(lambda c: {"json": detail})
    text, _ = await h.call("get_research", {"run_id": "r1", "wait_seconds": 0, "exclude_rows": [1], "sort": "importance"})
    assert "3 rows kept (left out #1)" in text
    assert "Counts over all 3 rows shown" in text
    assert "story_type: funding 2, layoffs 1" in text
    order = re.findall(r"^\| (\d) \|", text, re.M)
    assert order == ["2", "4", "3"]  # importance 4; then importance 3, newer first


async def test_get_research_takes_exclude_rows_as_json_text(setup):
    detail = {"run_id": "r1", "status": "succeeded", "kind": "events", "columns": ["company", "date"],
              "rows": [{"company": "A", "date": "2026-10-01"}, {"company": "B", "date": "2026-10-02"}]}
    h = setup(lambda c: {"json": detail})
    text, _ = await h.call("get_research", {"run_id": "r1", "wait_seconds": 0, "exclude_rows": "[2]", "sort": "newest"})
    assert "1 row kept (left out #2)" in text


async def test_instructions_say_open_windows_end_today(setup):
    from src.server import INSTRUCTIONS
    assert "a window without an end ends today" in INSTRUCTIONS


async def test_get_story_one_per_newsroom_and_earliest(setup):
    articles = [
        {"title": "a1", "domain": "yahoo.com", "url": "u1", "published_at": "2026-10-29T14:00:00Z"},
        {"title": "a2", "domain": "yahoo.com", "url": "u2", "published_at": "2026-10-29T15:00:00Z"},
        {"title": "b1", "domain": "reuters.com", "url": "u3", "published_at": "2026-10-29T16:00:00Z"},
        {"title": "c1", "domain": "huffpost.com", "url": "u4", "published_at": "2026-10-26T09:00:00+00:00"},
    ]
    h = setup(lambda c: {"json": {"story_id": "s", "articles_total": 4, "newsrooms": 3, "articles": articles}})
    text, _ = await h.call("get_story", {"story_id": "s", "limit": 2})
    assert h.calls[0].params["limit"] == "500"
    assert text.index("yahoo.com") < text.index("reuters.com")
    assert "a2" not in text.split("Earliest")[0]
    assert re.search(r"Earliest articles[\s\S]*huffpost\.com", text)


async def test_count_retries_timed_out_bucket_and_prints_peak(setup):
    n = {"i": 0}

    def reply(c):
        if c.body["from_date"].startswith("2026-11-02"):
            n["i"] += 1
            if n["i"] == 1:
                return {"status": 408, "json": {"message": "Request timed out."}}
            return {"json": {"total_hits": 50}}
        return {"json": {"total_hits": 10}}

    h = setup(reply)
    text, _ = await h.call("count_articles", {"queries": ["x"], "from": "2026-11-01", "to": "2026-11-02", "interval": "day"})
    assert "| 2026-11-02 | 50 |" in text
    assert "Peak day: x 2026-11-02 (50)" in text


async def test_count_refuses_more_than_60_calls(setup):
    h = setup(lambda c: {"json": {"total_hits": 1}})
    text, err = await h.call("count_articles", {"queries": ["a", "b", "c"], "from": "2026-09-01", "to": "2026-10-31"})
    assert err and "limit is 60" in text
    assert not h.calls


@pytest.mark.parametrize("status", [200, 401, 503])
async def test_api_key_never_leaks_into_results_or_logs(setup, capsys, monkeypatch, status):
    secret = "sk-SECRET-7f3a9c"
    monkeypatch.setenv("NEWSCATCHER_API_KEY", secret)
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    h = setup(lambda c: {"status": status, "json": {"message": "nope", "plan": "free"}})
    text, _ = await h.call("get_account")
    assert h.calls[0].headers["x-api-key"] == secret  # it was sent upstream...
    out = capsys.readouterr()
    assert secret not in text and secret not in out.err and secret not in out.out  # ...and nowhere else


def test_403_for_a_key_of_another_product_gets_no_plan_hint():
    from src.client import ApiError, error_hint

    other = ApiError(403, "This API key belongs to another NewsCatcher product and cannot be used with the News API.")
    assert error_hint(other, "news") == ""
    assert "plan does not include" in error_hint(ApiError(403, "Forbidden"), "news")


# ---------------------------------------------------------------- webhooks


async def test_start_research_sends_webhook_ids_and_dry_run_mentions_them(setup):
    h = setup(lambda c: {"status": 202, "json": {"run_id": "r1", "status": "queued", "kind": "events"}})
    text, _ = await h.call("start_research", {"query": "Bank M&A since Oct 1", "webhook_ids": ["w1", "w2"], "keep_updated": True})
    assert h.calls[0].body["webhook_ids"] == ["w1", "w2"]
    assert h.calls[0].body["keep_updated"] == {}  # the monitor gets the run's webhooks by default
    assert "Results go to 2 webhooks" in text
    await h.call("start_research", {"query": "Bank M&A since Oct 1"})
    assert "webhook_ids" not in h.calls[1].body
    h = setup(lambda c: {"json": {"credits_balance": 10_000}})
    text, _ = await h.call("start_research", {"query": "Bank M&A since Oct 1", "webhook_ids": "w1", "dry_run": True})
    assert all(c.method == "GET" for c in h.calls)
    assert "Webhooks: the results go to 1 webhook when the run succeeds" in text


async def test_create_monitor_sends_webhook_ids(setup):
    h = setup(lambda c: {"json": {"monitor_id": "m1", "kind": "companies", "name": "W", "companies": [{"domain": "a.com"}], "enabled": True}})
    text, _ = await h.call("create_monitor", {"companies": ["a.com"], "webhook_ids": ["w1"]})
    assert h.calls[0].body["webhook_ids"] == ["w1"]
    assert "also go to 1 webhook" in text


async def test_resend_results_for_runs_and_monitors(setup):
    h = setup(lambda c: {"status": 202, "json": {"webhook_ids": ["w1"]}})
    text, err = await h.call("resend_results", {"run_id": "r1"})
    assert not err and h.calls[0].url.endswith("/agent/runs/r1/webhooks/deliver") and h.calls[0].body == {}
    assert "Sending the results of run r1 to 1 webhook (w1)" in text
    await h.call("resend_results", {"monitor_id": "m1", "monitor_run_id": "mr1", "webhook_id": "w1"})
    assert h.calls[1].url.endswith("/agent/monitors/m1/webhooks/deliver")
    assert h.calls[1].body == {"webhook_id": "w1", "run_id": "mr1"}
    _, err = await h.call("resend_results", {"run_id": "r1", "monitor_id": "m1"})
    assert err and len(h.calls) == 2


async def test_resend_too_soon_is_not_retried(setup):
    h = setup(lambda c: {"status": 429, "json": {"code": "resend_too_soon", "message": "Sent less than a minute ago."}})
    text, err = await h.call("resend_results", {"run_id": "r1"})
    assert err and len(h.calls) == 1
    assert "Do not resend now" in text and "Rate limited" not in text


async def test_webhook_refusals_get_their_own_advice(setup):
    h = setup(lambda c: {"status": 403, "json": {"code": "webhook_not_allowed", "message": "Not your workspace's webhook."}})
    text, err = await h.call("start_research", {"query": "Bank M&A since Oct 1", "webhook_ids": ["w9"]})
    assert err and "Nothing was created or charged" in text and "plan does not include" not in text
    h = setup(lambda c: {"status": 409, "json": {"code": "no_webhooks", "message": "No webhooks attached."}})
    text, _ = await h.call("resend_results", {"run_id": "r1"})
    assert "No webhooks are attached" in text and "still going" not in text



# ---------------------------------------------------------------- search and paging (Agent API 1.17.0)


async def test_monitor_and_list_search_and_paging(setup):
    def responder(c):
        if c.url.split("?")[0].endswith("/monitors"):
            return {"json": {"monitors": [{"monitor_id": "m1", "kind": "companies", "name": "Fintech", "companies": [{"domain": "a.com"}],
                                           "enabled": False}], "next_cursor": "c2", "total": 7}}
        return {"json": {"lists": [{"list_id": "l1", "name": "Banks", "count": 3, "status": "ready"}], "next_cursor": None, "total": 1}}

    h = setup(responder)
    text, _ = await h.call("get_monitor", {"search": "fintech", "limit": 1})
    assert h.calls[0].params == {"q": "fintech", "limit": "1"}
    assert 'Showing 1 of 7. Next page: cursor="c2"' in text
    await h.call("get_monitor", {"cursor": "c2", "limit": 1})
    assert h.calls[1].params == {"limit": "1", "cursor": "c2"}
    text, _ = await h.call("get_company_list", {"search": "stripe.com", "limit": 20})
    assert h.calls[2].params == {"q": "stripe.com", "limit": "20"}
    assert '"Banks"' in text and "Next page" not in text
    await h.call("get_monitor", {})
    await h.call("get_company_list", {})
    assert not h.calls[3].params and not h.calls[4].params  # the plain listing sends no paging


async def test_search_with_no_match_says_so(setup):
    h = setup(lambda c: {"json": {"monitors": [], "next_cursor": None, "total": 0}} if "/monitors" in c.url else {"json": []})
    text, _ = await h.call("get_monitor", {"search": "nothing"})
    assert text == 'No monitors match "nothing".'
    text, _ = await h.call("get_company_list", {"search": "nothing"})
    assert text == 'No company lists match "nothing".'



# ---------------------------------------------------------------- continuing a run (Agent API 1.19.2)


def _events_run(rows: int, **extra):
    """A succeeded events run detail with ``rows`` rows."""
    return {"run_id": "r1", "kind": "events", "mode": "fast", "status": "succeeded", "columns": ["company", "url"],
            "rows": [{"company": f"c{i}", "url": f"https://x/{i}"} for i in range(rows)], "continuable": True, **extra}


async def test_continue_run_sends_the_new_total_and_points_to_both_runs(setup):
    def responder(c):
        if c.method == "POST":
            return {"status": 202, "json": {"run_id": "r1", "continuation_id": "c1", "status": "queued", "rows": 50, "max_rows": 100}}
        return {"json": _events_run(50)}

    h = setup(responder)
    text, err = await h.call("start_research", {"continue_run_id": "r1"})
    assert not err
    post = [c for c in h.calls if c.method == "POST"]
    assert len(post) == 1 and post[0].url.endswith("/agent/runs/r1/continue") and post[0].body == {"max_rows": 100}
    for s in ("continuation c1", "from 50 rows to up to 100", "at most 500 credits", "left out",
              'get_research(run_id="c1"', 'get_research(run_id="r1") has every row'):
        assert s in text
    assert "$" not in text


async def test_continue_run_is_never_retried_after_a_5xx(setup):
    h = setup(lambda c: {"status": 503, "json": {"message": "Unavailable"}} if c.method == "POST" else {"json": _events_run(50)})
    text, err = await h.call("start_research", {"continue_run_id": "r1", "add_rows": 30})
    assert err and len([c for c in h.calls if c.method == "POST"]) == 1
    assert "may have gone through" in text


async def test_continue_dry_run_prices_only_the_extra_blocks(setup):
    def responder(c):
        if "/subscription" in c.url:
            return {"json": {"credits_balance": 9000}}
        return {"json": _events_run(50, mode="standard")}

    h = setup(responder)
    text, _ = await h.call("start_research", {"continue_run_id": "r1", "add_rows": 100, "dry_run": True})
    assert all(c.method == "GET" for c in h.calls)
    for s in ("nothing was started or charged", "50 rows now, up to 150 after (+100)", "can be continued now",
              "at most 3,000 credits", "Balance: 9,000 credits", "Standard runs take"):
        assert s in text
    # 30 rows + 20 stay inside the 50 rows a run includes: nothing to pay.
    h = setup(lambda c: {"json": _events_run(30, continuable=False)} if "/runs/" in c.url else {"json": {}})
    text, _ = await h.call("start_research", {"continue_run_id": "r1", "add_rows": 20, "dry_run": True})
    assert "Cost: free" in text and "cannot be continued: it found fewer rows" in text


async def test_continue_run_limits_and_wrong_runs(setup):
    h = setup(lambda c: {"json": _events_run(50)})
    _, err = await h.call("start_research", {"continue_run_id": "r1", "query": "more layoffs"})
    assert err and not h.calls
    # One continuation adds up to the plan's rows per run (100).
    _, err = await h.call("start_research", {"continue_run_id": "r1", "add_rows": 101})
    assert err and not h.calls
    # Capped at 1,000 rows in all.
    h = setup(lambda c: {"status": 202, "json": {"continuation_id": "c1", "status": "queued"}} if c.method == "POST" else {"json": _events_run(950)})
    await h.call("start_research", {"continue_run_id": "r1", "add_rows": 100})
    assert h.calls[-1].body == {"max_rows": 1000}
    h = setup(lambda c: {"status": 202, "json": {"continuation_id": "c1", "status": "queued"}} if c.method == "POST" else {"json": _events_run(990)})
    await h.call("start_research", {"continue_run_id": "r1", "add_rows": 100})
    assert h.calls[-1].body == {"max_rows": 1000}
    h = setup(lambda c: {"json": _events_run(1000)})
    text, err = await h.call("start_research", {"continue_run_id": "r1"})
    assert err and "most a run can have" in text and all(c.method == "GET" for c in h.calls)
    h = setup(lambda c: {"json": _events_run(20, run_id="c1", continue_of="r1", continuable=None)})
    text, err = await h.call("start_research", {"continue_run_id": "c1"})
    assert err and 'continue_run_id="r1"' in text and all(c.method == "GET" for c in h.calls)
    h = setup(lambda c: {"json": {"run_id": "r2", "kind": "companies", "status": "succeeded", "rows": []}})
    text, err = await h.call("start_research", {"continue_run_id": "r2"})
    assert err and "Only events runs" in text


async def test_continue_refusals_get_their_own_advice(setup):
    def responder(c):
        if c.method == "POST":
            return {"status": 409, "json": {"code": "run_not_continuable", "message": "This run found 10 of the 50 rows it asked for."}}
        return {"json": _events_run(10, continuable=False)}

    text, err = await setup(responder).call("start_research", {"continue_run_id": "r1"})
    assert err and "found 10 of the 50" in text and "Nothing was started or charged" in text and "still going" not in text
    h = setup(lambda c: {"status": 409, "json": {"code": "run_busy", "message": "Already being continued."}}
              if c.method == "POST" else {"json": _events_run(50)})
    text, _ = await h.call("start_research", {"continue_run_id": "r1"})
    assert "already being continued" in text and "still going" not in text


async def test_get_research_shows_continuations_and_the_more_rows_hint(setup):
    run = _events_run(
        60,
        continuations=[{"continuation_id": "c0", "status": "succeeded", "max_rows": 100, "rows_added": 10, "found": 50,
                        "duplicates": {"url": 30, "key": 5, "same_event": 5}}],
    )
    text, _ = await setup(lambda c: {"json": run}).call("get_research", {"run_id": "r1", "wait_seconds": 0})
    assert "Continued 1 time: succeeded, +10 rows (40 it found were already in the run)." in text
    assert 'start_research(continue_run_id="r1", add_rows=50)' in text
    busy = _events_run(60, continuable=False, continuation={"continuation_id": "c2", "max_rows": 110, "rows_before": 60})
    text, _ = await setup(lambda c: {"json": busy}).call("get_research", {"run_id": "r1", "wait_seconds": 0})
    assert 'Being continued: continuation c2, up to 110 rows in all. get_research(run_id="c2")' in text
    assert "continue_run_id" not in text
    # Not continuable (found fewer than it asked for): no hint.
    text, _ = await setup(lambda c: {"json": _events_run(10, continuable=False)}).call("get_research", {"run_id": "r1", "wait_seconds": 0})
    assert "continue_run_id" not in text and "Continued" not in text


async def test_get_research_on_a_continuation_points_to_its_run(setup):
    cont = _events_run(50, run_id="c1", continue_of="r1", continuable=None)
    text, _ = await setup(lambda c: {"json": cont}).call("get_research", {"run_id": "c1", "wait_seconds": 0})
    assert 'A continuation of run r1: once it succeeds, its new rows are in get_research(run_id="r1")' in text
    running = {**cont, "status": "running", "rows": []}
    text, _ = await setup(lambda c: {"json": running}).call("get_research", {"run_id": "c1", "wait_seconds": 0})
    assert "A continuation: it adds rows to run r1." in text


async def test_monitor_listing_marks_the_free_monitor(setup):
    ms = [{"monitor_id": "m1", "kind": "companies", "name": "A", "companies": [{"domain": "a.com"}], "enabled": True, "free": True},
          {"monitor_id": "m2", "kind": "companies", "name": "B", "companies": [{"domain": "b.com"}], "enabled": True, "free": False}]
    text, _ = await setup(lambda c: {"json": {"monitors": ms}}).call("get_monitor", {})
    first, second = text.splitlines()[:2]
    assert "free (the account's free monitor: its runs cost nothing)" in first and "free" not in second


async def test_add_rows_schema_is_bounded():
    tools = {t.name: t for t in await list_tools(build_server(load_config()))}
    p = tools["start_research"].input_schema["properties"]
    assert p["add_rows"]["maximum"] == 100 and p["add_rows"]["minimum"] == 1 and p["add_rows"]["default"] == 50
    assert p["continue_run_id"]["anyOf"][0]["type"] == "string"
