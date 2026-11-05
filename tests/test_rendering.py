"""Pure rendering and date helpers, ported from the TypeScript suite."""

from datetime import datetime, timezone

from src.lenient import as_items, as_list, parse_json_text
from src.tools.news import make_buckets, parse_day, render_search
from src.tools.research import render_run, sort_rows, summarize_rows


def test_daily_weekly_monthly_buckets():
    s = parse_day("2026-10-01")
    e = parse_day("2026-10-07", end_of_day=True)
    assert len(make_buckets(s, e, "day")) == 7
    assert len(make_buckets(s, e, "week")) == 1
    assert [b["label"] for b in make_buckets(s, parse_day("2026-12-31", end_of_day=True), "month")] == ["2026-10", "2026-11", "2026-12"]


def test_partial_last_bucket():
    b = make_buckets(parse_day("2026-11-03"), datetime(2026, 11, 4, 12, tzinfo=timezone.utc), "day")
    assert [x["partial"] for x in b] == [False, True]


def test_relative_dates():
    now = datetime(2026, 11, 5, 7, 0, tzinfo=timezone.utc)
    assert parse_day("7d", now=now) == datetime(2026, 10, 29, tzinfo=timezone.utc)
    assert parse_day("14 days ago", now=now) == datetime(2026, 10, 22, tzinfo=timezone.utc)
    assert parse_day("12h", now=now) == datetime(2026, 11, 4, 19, tzinfo=timezone.utc)
    assert parse_day("yesterday", now=now) == datetime(2026, 11, 4, tzinfo=timezone.utc)
    assert parse_day("today", end_of_day=True, now=now) == now
    assert parse_day("nonsense", now=now) is None
    assert parse_day("2026-02-30", now=now) is None


def test_render_search_story_ids_newsrooms_translations():
    t = render_search(
        {
            "effort": "medium",
            "count": 1,
            "window": {"search_window": "7d", "from": "2026-10-28T00:00:00Z", "to": "2026-11-04T00:00:00Z"},
            "results": [{
                "title": "Airbus-Aktie steigt", "title_en": "Airbus shares rise", "source": {"name": "Investing.com"},
                "published_at": "2026-10-29T10:47:00+00:00", "country": "DE", "language": "de",
                "story": {"id": "s1", "newsrooms": 39}, "summary_en": "Shares rose.", "url": "https://x",
            }],
        },
        "Airbus",
    )
    assert "[EN: Airbus shares rise]" in t
    assert "story s1 (39 newsrooms)" in t
    assert "2026-10-29 10:47 UTC" in t


def test_render_running_and_finished_runs():
    running = render_run({"run_id": "r", "kind": "events", "mode": "fast", "status": "running",
                          "phases": [{"label": "Planning", "status": "done", "seconds": 40}, {"label": "Searching", "status": "active"}]}, 0, 25)
    assert "Still running" in running and 'say "refresh"' in running
    done = render_run({"run_id": "r", "kind": "events", "mode": "fast", "status": "succeeded", "columns": ["company", "source_url"],
                       "rows": [{"company": "A", "source_url": "u1"}, {"company": "B", "source_url": "u2"}]}, 0, 1)
    assert "| company | source_url |" in done
    assert "Rows 1–1 of 2. More: rows_offset=1." in done
    assert "export_research" not in done


def test_batch_progress_in_words():
    t = render_run({"batch_id": "b1", "kind": "companies", "status": "running",
                    "progress": {"runs_done": 1, "runs_total": 3, "companies_done": 20, "companies_total": 60}}, 0, 25)
    assert "Batch b1" in t
    assert "20/60 companies, 1/3 runs done" in t


def test_summarize_rows():
    cols = ["company", "company_domain", "amount", "currency", "round", "lead_investor", "other_investors", "threat_actor", "event_date", "source_url"]
    rows = [
        {"company": "A", "company_domain": "a.com", "amount": 1000000, "currency": "USD", "round": "Series B", "lead_investor": "ICONIQ", "other_investors": "Accel; NVIDIA", "threat_actor": "Qilin (claimed)", "event_date": "2026-10-02", "source_url": "https://x"},
        {"company": "B", "company_domain": "b.com", "amount": "2,000,000", "currency": "USD", "round": "Series B", "lead_investor": "NVIDIA", "other_investors": "ICONIQ", "threat_actor": "Qilin", "event_date": "2026-10-20", "source_url": "https://y"},
        {"company": "C", "company_domain": "c.com", "amount": "", "currency": "EUR", "round": "Seed", "lead_investor": "", "other_investors": "", "threat_actor": "", "event_date": "2026-10-09", "source_url": "https://z"},
    ]
    s = summarize_rows(cols, rows)
    for part in ("Counts over all 3 rows", "event_date 2026-10-02 → 2026-10-20", "round: Series B 2, Seed 1", "threat_actor: Qilin 2",
                 "investors in 2+ rows (any role): ICONIQ 2, NVIDIA 2", "amount disclosed: USD 3M over 2 rows; 1 undisclosed"):
        assert part in s
    assert "company_domain" not in s and "source_url:" not in s
    assert summarize_rows(cols, rows[:1]) == ""


def test_sort_rows_newest_first_undated_last():
    d = {"columns": ["org", "event_date"], "rows": [{"org": "a", "event_date": "2026-10-01"}, {"org": "b", "event_date": ""}, {"org": "c", "event_date": "2026-10-20"}]}
    assert [r["org"] for r in sort_rows(d, "newest")["rows"]] == ["c", "a", "b"]
    assert [r["org"] for r in sort_rows(d, "oldest")["rows"]] == ["a", "c", "b"]
    assert sort_rows(d, "original") is d
    assert sort_rows(d, "newest")["rows"][0]["__n"] == 3
    t = render_run({"run_id": "r", "status": "succeeded", **sort_rows(d, "newest")}, 0, 25)
    assert "| 3 | c | 2026-10-20 |" in t
    assert "__n" not in t


def test_lenient_parsing():
    assert parse_json_text('["a","b"]') == ["a", "b"]
    assert parse_json_text("true") is True
    assert parse_json_text("[broken") == "[broken"
    assert as_list("en, de") == ["en", "de"]
    assert as_items('"Tesla, Inc."') == ['"Tesla, Inc."']
    assert as_items("") == []


def test_api_urls_from_split_env_vars(monkeypatch):
    import pytest

    from src.config import load_config

    cfg = load_config()
    assert cfg.news_api_url == "https://api.newscatcherapi.com/news-api"
    assert cfg.agent_api_url == "https://api.newscatcherapi.com/agent"
    monkeypatch.setenv("NEWSCATCHER_NEWS_API_URL", "dev-api.example.com")
    monkeypatch.setenv("NEWSCATCHER_NEWS_API_PORT", "8443")
    monkeypatch.setenv("NEWSCATCHER_NEWS_API_ENDPOINT", "/news-api/")
    monkeypatch.setenv("NEWSCATCHER_AGENT_API_URL", "dev-api.example.com")
    monkeypatch.setenv("NEWSCATCHER_AGENT_API_PORT", "443")
    cfg = load_config()
    assert cfg.news_api_url == "https://dev-api.example.com:8443/news-api"
    assert cfg.agent_api_url == "https://dev-api.example.com/agent"
    monkeypatch.setenv("NEWSCATCHER_NEWS_API_URL", "https://dev-api.example.com")
    with pytest.raises(ValueError, match="bare host"):
        load_config()
