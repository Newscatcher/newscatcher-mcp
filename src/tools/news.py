"""News tools: search_news, list_articles, count_articles, get_story, get_account."""

import re
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any, Literal
from urllib.parse import quote

from fastmcp import FastMCP
from pydantic import Field

from src.client import ApiError
from src.config import Config
from src.formatting import clip, num, plural, to_json, when
from src.lenient import ItemList, TokenList
from src.tools.common import Call, UserError, register
from src.tools.params import (
    BooleanQuery,
    Countries,
    ExcludeCountries,
    ExcludeLanguages,
    ExcludeSources,
    Format,
    Languages,
    Sources,
    TopSources,
    drop_none,
    items,
    news_filters,
    search_in,
)

READ_ONLY = {"readOnlyHint": True, "idempotentHint": True}
Dim = Literal["source", "author", "country", "language"]


def archive_error(err: ApiError) -> ApiError:
    """``/articles`` answers 503 when the archive part of the backend is down; say what still works.

    Args:
        err (ApiError): The error from ``/articles``.

    Returns:
        ApiError: The error to raise.
    """
    if err.status == 503:
        return ApiError(
            503,
            f"{err.message} Windows reaching back more than ~30 days use the news archive, which is unavailable right "
            "now. Retrying the same window will fail again: use a window inside the last 30 days, and tell the user "
            "older coverage could not be checked.",
            "archive_unavailable",
            err.correlation_id,
        )
    return err


async def post_articles(call: Call, body: dict[str, Any]) -> Any:
    """POST /articles, explaining archive outages.

    Args:
        call (Call): The tool call.
        body (dict[str, Any]): Request body.

    Returns:
        Any: Response body.

    Raises:
        ApiError: With the archive hint on a 503.
    """
    try:
        return await call.client.post("news", "/articles", body)
    except ApiError as err:
        raise archive_error(err) from err


def register_news_tools(mcp: FastMCP, config: Config) -> None:
    """Register the news toolset.

    Args:
        mcp (FastMCP): The server.
        config (Config): Server settings.
    """

    # ------------------------------------------------------------------ search_news
    @register(
        mcp,
        config,
        name="search_news",
        title="Search news",
        description=(
            "Search recent news (last 30 days, every language) and get the best articles, ranked and grouped into stories, "
            "each with a one-line summary, source, date and link. "
            "Use it for anything news-shaped: what happened, latest developments, coverage of a company, person, topic or "
            "event, or checking if something was reported. "
            "It keeps to real news sources, groups articles into stories (with a newsroom count), translates titles and "
            "summaries, and takes exact time windows. "
            "For an exact count or every matching article use list_articles; for older news (up to 12 months) use "
            "list_articles; to build a dataset or watch companies use start_research."
        ),
        toolset="news",
        api="news",
        annotations=READ_ONLY,
        always_load=True,
    )
    async def search_news(
        call: Call,
        query: Annotated[
            str,
            Field(
                min_length=1,
                max_length=500,
                description=(
                    'What to find: a plain-language question or keywords, any language (e.g. "Nvidia earnings guidance", '
                    '"who is acquiring European banks?"). Upper-case NOT drops a term: "Apple NOT iPhone".'
                ),
            ),
        ],
        window: Annotated[
            str | None,
            Field(
                description=(
                    'How far back from now: e.g. "2h", "1d", "7d" (default), up to "30d" (longer windows are cut to 30 '
                    "days; use list_articles for older news)."
                )
            ),
        ] = None,
        effort: Annotated[
            Literal["low", "medium", "high"],
            Field(
                description=(
                    "Ranking effort and price: low (1 credit, ~4 s), medium (default, 5 credits, ~8 s, reranked), high "
                    "(10 credits, ~25 s, LLM-judged, merges duplicate stories)."
                )
            ),
        ] = "medium",
        limit: Annotated[
            int, Field(ge=1, le=100, description="Articles to return (default 10; the free plan allows up to 50).")
        ] = 10,
        group: Annotated[
            Literal["diverse", "story", "all"],
            Field(
                description=(
                    "diverse (default): best articles with repeats of one story discounted; story: one article per story "
                    "(widest coverage of distinct events); all: every matching article."
                )
            ),
        ] = "diverse",
        sort: Annotated[Literal["relevance", "newest"], Field(description="relevance (default) or newest first.")] = "relevance",
        min_newsrooms: Annotated[
            int | None,
            Field(ge=0, description="Only stories covered by at least this many newsrooms (a proxy for importance)."),
        ] = None,
        include_non_news: Annotated[
            bool,
            Field(description="Also return non-news content (press releases, blogs, opinion). Default false: real news only."),
        ] = False,
        languages: Languages = None,
        countries: Countries = None,
        sources: Sources = None,
        exclude_languages: ExcludeLanguages = None,
        exclude_countries: ExcludeCountries = None,
        exclude_sources: ExcludeSources = None,
        format: Format = "text",
    ) -> str:
        """Ranked, story-grouped search over the last 30 days."""
        search_window, note = clamp_window(window)
        body = drop_none(
            {
                "q": query,
                "effort": effort,
                "limit": limit,
                "collapse": "duplicates" if group == "all" else group,
                "sort_by": "published_at" if sort == "newest" else "relevancy",
                "search_window": search_window,
                "min_newsrooms": min_newsrooms,
                "content_type": "all" if include_non_news else None,
                **news_filters(languages, countries, sources, exclude_languages, exclude_countries, exclude_sources),
            }
        )
        data = await call.client.post("news", "/search", body)
        if format == "json":
            return to_json({**data, **({"note": note} if note else {})})
        return (f"{note}\n" if note else "") + render_search(data, query)

    # ------------------------------------------------------------------ list_articles
    @register(
        mcp,
        config,
        name="list_articles",
        title="List matching articles",
        description=(
            "List EVERY article that matches a boolean query over the last 12 months, newest first, with an exact total "
            "count, paged (up to 1,000 per query). "
            'Use it for completeness and counting: "how many articles mention X", "all coverage of Y since October", '
            "older news beyond 30 days, monitoring checklists, exports. tally counts matches by outlet, author, country or "
            "language (who covers a topic). "
            "Precise keyword/boolean matching, not relevance ranking: for the best answers to a question use search_news. "
            "5 credits per call."
        ),
        toolset="news",
        api="news",
        annotations=READ_ONLY,
    )
    async def list_articles(
        call: Call,
        query: Annotated[
            BooleanQuery,
            Field(
                description=(
                    'Boolean query: AND, OR, NOT, parentheses, "exact phrases", +must, -mustnot, wild*cards, '
                    'NEAR("a", "b", 5). Example: "Nvidia" AND (earnings OR guidance) NOT "stock split".'
                )
            ),
        ],
        from_: Annotated[
            str | None,
            Field(
                alias="from",
                description='Start: ISO date/time ("2026-10-01") or a phrase ("30 days ago"). Default: 7 days ago. Up to 12 months back.',
            ),
        ] = None,
        to: Annotated[
            str | None,
            Field(
                description=(
                    "End: ISO date/time or phrase. Default: now. When paging, pass the window end from the first page so "
                    "every page covers the same articles."
                )
            ),
        ] = None,
        search_in: search_in(  # type: ignore[valid-type]
            "Where the query is matched (default title_body). *_translated fields match the English translation of non-English articles."
        ) = None,
        sort: Annotated[
            Literal["newest", "oldest", "relevance", "source_rank"],
            Field(description="Order: newest (default), oldest, relevance, or source_rank (biggest publishers first)."),
        ] = "newest",
        page: Annotated[
            int, Field(ge=1, description="Page number, from 1. page × page_size can reach the first 1,000 articles of a query.")
        ] = 1,
        page_size: Annotated[int, Field(ge=1, le=100, description="Articles per page (default 20, up to 100).")] = 20,
        count_only: Annotated[bool, Field(description="Return only the exact number of matching articles (no list).")] = False,
        exclude_duplicates: Annotated[bool, Field(description="Leave out syndicated copies of an article.")] = False,
        top_sources: TopSources = None,
        max_source_rank: Annotated[
            int | None,
            Field(ge=1, le=999999, description="Only publishers ranked at or better than this traffic rank (1 = biggest)."),
        ] = None,
        min_words: Annotated[int | None, Field(ge=0, description="Only articles with at least this many words.")] = None,
        tally: Annotated[
            items(Dim, min_length=1, max_length=4) | None,  # type: ignore[operator]
            TokenList,
            Field(
                description=(
                    "Instead of listing, count the matching articles by outlet, author (bylines that are people), country "
                    'and/or language, in one pass: e.g. ["source","country","language"]. Outlets and authors come with '
                    "their latest article. Who covers a topic, media lists, coverage mix."
                ),
            ),
        ] = None,
        tally_pages: Annotated[
            int, Field(ge=1, le=10, description="With tally: pages of 100 newest articles to count (default 3; 5 credits each).")
        ] = 3,
        languages: Languages = None,
        countries: Countries = None,
        sources: Sources = None,
        exclude_languages: ExcludeLanguages = None,
        exclude_countries: ExcludeCountries = None,
        exclude_sources: ExcludeSources = None,
        format: Format = "text",
    ) -> str:
        """Exact boolean listing over 12 months, or a tally of the matches."""
        sort_map = {"newest": "published_at", "oldest": "-published_at", "relevance": "relevancy", "source_rank": "rank"}
        body = drop_none(
            {
                "q": query,
                "from_date": from_,
                "to_date": to,
                "search_in": search_in or None,
                "sort_by": sort_map[sort],
                "page": 1 if count_only else page,
                "page_size": 1 if count_only else page_size,
                "exclude_duplicates": True if exclude_duplicates else None,
                "predefined_sources": top_sources,
                "to_rank": max_source_rank,
                "word_count_min": min_words,
                **news_filters(languages, countries, sources, exclude_languages, exclude_countries, exclude_sources),
            }
        )
        if tally and not count_only:
            return await tally_articles(call, query, tally, tally_pages, body)
        data = await post_articles(call, body)
        if format == "json":
            if count_only:
                return to_json({"query": data.get("query"), "total_hits": data.get("total_hits"), "window": data.get("window")})
            return to_json(data)
        return render_articles(data, count_only)

    # ------------------------------------------------------------------ count_articles
    @register(
        mcp,
        config,
        name="count_articles",
        title="Count articles over time",
        description=(
            "Exact article counts over time for 1–5 boolean queries: a daily, weekly or monthly timeline of news volume, "
            "and share of voice between queries (companies, brands, topics). "
            'Use it for trends, spikes, "is coverage rising", comparing competitors, or charting attention around an event. '
            "Each bucket × query is one 5-credit call (at most 60 calls), so a 30-day daily timeline for 2 queries is 60 "
            "calls / 300 credits and takes about a minute."
        ),
        toolset="news",
        api="news",
        annotations=READ_ONLY,
    )
    async def count_articles(
        call: Call,
        queries: Annotated[
            list[BooleanQuery],
            ItemList,
            Field(
                min_length=1,
                max_length=5,
                description='1 to 5 boolean queries to count (same syntax as list_articles), e.g. ["Tesla", "Rivian", "Lucid"] for share of voice.',
            ),
        ],
        from_: Annotated[
            str,
            Field(
                alias="from",
                description='Start of the period: ISO date ("2026-09-01") or relative ("14d", "30 days ago"); up to 12 months back.',
            ),
        ],
        to: Annotated[
            str | None, Field(description='End of the period: ISO date or "today"/"yesterday" (default: now).')
        ] = None,
        interval: Annotated[
            Literal["day", "week", "month"], Field(description="Bucket size: day (default), week or month.")
        ] = "day",
        search_in: search_in(  # type: ignore[valid-type]
            'Where queries are matched (default title_body). Use ["title"] to count only headline mentions.'
        ) = None,
        exclude_duplicates: Annotated[bool, Field(description="Leave out syndicated copies.")] = False,
        languages: Languages = None,
        countries: Countries = None,
        sources: Sources = None,
        exclude_languages: ExcludeLanguages = None,
        exclude_countries: ExcludeCountries = None,
        exclude_sources: ExcludeSources = None,
        format: Format = "text",
    ) -> str:
        """Timeline of exact counts per query."""
        now = datetime.now(timezone.utc)
        start = parse_day(from_, now=now)
        end = parse_day(to, end_of_day=True, now=now) if to else now
        start_note = ""
        earliest = now - timedelta(days=365)
        if start and start < earliest:
            start = datetime(earliest.year, earliest.month, earliest.day, tzinfo=timezone.utc) + timedelta(days=1)
            start_note = f"Start moved to {start.date().isoformat()}: counts reach back 12 months at most.\n"
        if not start or not end or start >= end:
            raise UserError('from must be a date before to: an ISO date (from="2026-10-01") or relative (from="14d").')
        buckets = make_buckets(start, end, interval)
        calls = len(buckets) * len(queries)
        if calls > 60:
            raise UserError(
                f"That is {calls} calls ({len(buckets)} {interval}s × {len(queries)} queries); the limit is 60. "
                "Use a wider interval or a shorter period."
            )
        filters = news_filters(languages, countries, sources, exclude_languages, exclude_countries, exclude_sources)
        counts: list[list[int | None]] = [[] for _ in queries]
        unavailable = timed_out = out_of_time = done = 0
        for qi, q in enumerate(queries):
            for b in buckets:
                value: int | None = None
                if call.time_left() <= 0:
                    # Answer with what was counted rather than being cut off by the hosting time limit.
                    out_of_time += 1
                else:
                    body = drop_none(
                        {
                            "q": q,
                            "from_date": iso(b["from"]),
                            "to_date": iso(b["to"]),
                            "page": 1,
                            "page_size": 1,
                            "search_in": search_in or None,
                            "exclude_duplicates": True if exclude_duplicates else None,
                            **filters,
                        }
                    )
                    for attempt in (1, 2):
                        try:
                            data = await call.client.post("news", "/articles", body)
                            value = int((data or {}).get("total_hits") or 0)
                            break
                        except ApiError as err:
                            # A busy bucket can time out (408): try once more. An archive outage (503) hits only the
                            # older buckets. Either way keep the rest of the timeline.
                            if err.status not in (503, 408):
                                raise
                            if err.status == 408 and attempt == 1:
                                continue
                            if err.status == 408:
                                timed_out += 1
                            else:
                                unavailable += 1
                            break
                counts[qi].append(value)
                done += 1
                await call.progress(done, calls, f"{q}: {b['label']}")
        if unavailable == calls:
            raise archive_error(ApiError(503, "The news search backend is not available."))
        if unavailable + timed_out == calls:
            raise ApiError(408, "Every count timed out. Use a narrower query or a weekly interval.")

        def n(v: int | None) -> str:
            """Render a count or n/a."""
            return "n/a" if v is None else num(v)

        totals = [sum(v or 0 for v in counts[qi]) for qi in range(len(queries))]
        gaps = [
            f"{plural(unavailable, 'bucket')} reaching back more than ~30 days (the news archive is unavailable right now)"
            if unavailable
            else "",
            f"{plural(timed_out, 'bucket')} that timed out twice (busy query; a weekly interval or a narrower query helps)"
            if timed_out
            else "",
            f"{plural(out_of_time, 'bucket')} left when the server's {config.max_call_seconds} s time limit for one call "
            "ran out (a wider interval, a shorter period or fewer queries fits)"
            if out_of_time
            else "",
        ]
        gaps = [g for g in gaps if g]
        gap_note = (
            f"\nn/a: could not count {' and '.join(gaps)}; totals and shares cover the counted buckets only. Tell the user."
            if gaps
            else ""
        )
        peaks: list[str] = []
        for qi, q in enumerate(queries):
            best = -1
            for i, v in enumerate(counts[qi]):
                if v is not None and (best < 0 or v > (counts[qi][best] or -1)):
                    best = i
            if best >= 0:
                b = buckets[best]
                peaks.append(f"{q} {b['label']}{' (partial)' if b['partial'] else ''} ({n(counts[qi][best])})")
        peak_line = f"\nPeak {interval}: {'; '.join(peaks)}" if len(buckets) > 1 and peaks else ""
        if format == "json":
            return to_json(
                {
                    "interval": interval,
                    "unavailable_buckets": unavailable or None,
                    "timed_out_buckets": timed_out or None,
                    "out_of_time_buckets": out_of_time or None,
                    "buckets": [
                        {
                            "label": b["label"],
                            "from": iso(b["from"]),
                            "to": iso(b["to"]),
                            **({"partial": True} if b["partial"] else {}),
                            "counts": {q: counts[qi][i] for qi, q in enumerate(queries)},
                        }
                        for i, b in enumerate(buckets)
                    ],
                    "totals": dict(zip(queries, totals)),
                    "calls": calls,
                }
            )
        header = f"| {interval} | {' | '.join(queries)} |\n|---|{'|'.join('---:' for _ in queries)}|"
        rows = [
            f"| {b['label']}{' (partial, to ' + when(iso(b['to'])) + ')' if b['partial'] else ''} | "
            + " | ".join(n(counts[qi][i]) for qi in range(len(queries)))
            + " |"
            for i, b in enumerate(buckets)
        ]
        all_total = sum(totals) or 1
        share = (
            "\nShare of voice: " + ", ".join(f"{q} {100 * totals[qi] / all_total:.1f}%" for qi, q in enumerate(queries))
            if len(queries) > 1
            else ""
        )
        label = {"day": "daily", "week": "weekly", "month": "monthly"}[interval]
        made = calls - unavailable - timed_out - out_of_time
        return (
            f"{start_note}Exact article counts, {label}, {buckets[0]['label']} → {buckets[-1]['label']} "
            f"(UTC, {plural(len(buckets), interval)}).\n{header}\n" + "\n".join(rows) + "\n"
            f"| total | {' | '.join(num(t) for t in totals)} |{share}{peak_line}{gap_note}\n{plural(made, 'call')} × 5 credits."
        )

    # ------------------------------------------------------------------ get_story
    @register(
        mcp,
        config,
        name="get_story",
        title="Get a story",
        description=(
            "Every article of one story (the coverage of one event) from search_news: how many newsrooms covered it, when it "
            "first and last appeared, each article's publisher, date, headline and link (best sources first), and the "
            "earliest articles. "
            "Use it to gauge how big a story is, find the original or most authoritative source, or collect all coverage "
            "of an event. 1 credit."
        ),
        toolset="news",
        api="news",
        annotations=READ_ONLY,
    )
    async def get_story(
        call: Call,
        story_id: Annotated[str, Field(min_length=1, description='A story id from a search_news result (the "story" field).')],
        limit: Annotated[int, Field(ge=1, le=500, description="Articles to list (default 20, up to 500).")] = 20,
        format: Format = "text",
    ) -> str:
        """All articles of one story, one per newsroom first, plus the earliest ones."""
        # One call costs 1 credit whatever the size, so fetch the whole story and pick what to show here.
        data = await call.client.get("news", f"/stories/{quote(story_id, safe='')}", {"limit": 500})
        articles: list[dict[str, Any]] = data.get("articles") or []
        # One article per newsroom first (the API ranks syndicated copies of one outlet together), then the rest.
        seen: set[Any] = set()
        first_per_domain: list[dict[str, Any]] = []
        rest: list[dict[str, Any]] = []
        for a in articles:
            if a.get("domain") in seen:
                rest.append(a)
            else:
                seen.add(a.get("domain"))
                first_per_domain.append(a)
        best = (first_per_domain + rest)[:limit]
        dated = [a for a in articles if a.get("published_at")]
        earliest = sorted(dated, key=lambda a: _ts(a["published_at"]))[:3]
        if format == "json":
            return to_json({**data, "articles": best, "earliest": earliest})

        def line(a: dict[str, Any], i: int) -> str:
            """One article line."""
            lang = f" · {a['language']}" if a.get("language") and a.get("language") != "en" else ""
            return f"{i + 1}. {clip(a.get('title'), 160)}\n   {a.get('domain')} · {when(a.get('published_at'))}{lang}\n   {a.get('url')}"

        shown = {a.get("url") for a in best}
        first_out = ""
        if any(a.get("url") not in shown for a in earliest):
            first_out = (
                "\nEarliest articles (a live blog or an updated page can carry an older timestamp than the event):\n"
                + "\n".join(
                    f"- {when(a.get('published_at'))} · {a.get('domain')} · {clip(a.get('title'), 140)}\n  {a.get('url')}"
                    for a in earliest
                )
            )
        total = int(data.get("articles_total") or 0)
        return (
            f"Story {data.get('story_id')}: {plural(total, 'distinct article')} from "
            f"{plural(int(data.get('newsrooms') or 0), 'newsroom')}, first seen {when(data.get('first_seen'))}, "
            f"last seen {when(data.get('last_seen'))}.\n"
            "Best sources first, one article per newsroom:\n"
            + ("\n".join(line(a, i) for i, a in enumerate(best)) if best else "(no articles)")
            + (f"\n… {total - len(best)} more (raise limit, up to 500)." if total > len(best) else "")
            + first_out
        )

    # ------------------------------------------------------------------ get_account
    @register(
        mcp,
        config,
        name="get_account",
        title="Account, credits and limits",
        description=(
            "Your NewsCatcher plan, credit balance and limits: credits per search effort, results per call, how far back "
            "each endpoint reaches, and rate limits. Free. "
            "Use it before large jobs, when a call fails with 402/403/429, or to explain costs."
        ),
        toolset="news",
        api="news",
        annotations=READ_ONLY,
    )
    async def get_account(call: Call) -> str:
        """Plan, balance and limits."""
        s = await call.client.get("news", "/subscription")
        c = s.get("credits_per_search") or {}
        art = s.get("articles") or {}
        lines = [
            f"Plan: {s.get('plan')} · credit balance: {num(float(s.get('credits_balance') or 0))} NCC",
            f"search_news: {c.get('low')}/{c.get('medium')}/{c.get('high')} credits (low/medium/high) · up to "
            f"{s.get('max_articles_per_page')} results · last {s.get('historical_days')} days · "
            f"{s.get('shared_requests_per_second')} req/s",
            f"list_articles / count_articles: {art.get('credits_per_request')} credits per call · "
            f"{art.get('max_articles_per_page')} per page, first {art.get('max_articles_per_query')} per query · last "
            f"{art.get('historical_days')} days · {art.get('requests_per_second')} req/s",
            f"get_story: {s['story'].get('credits_per_request')} credit per call" if s.get("story") else "",
            f"Daily limit: {s.get('daily_requests_used')}/{s.get('daily_request_limit')}"
            if s.get("daily_request_limit")
            else "No daily request limit.",
            "Research agent runs and monitors are billed from the same balance when they finish (failed or empty runs are free).",
        ]
        return "\n".join(x for x in lines if x)


# ---------------------------------------------------------------------- helpers


async def fetch_all(call: Call, body: dict[str, Any], max_pages: int) -> dict[str, Any]:
    """Page through matches (100 per call, first 1,000 at most) with the window end pinned after the first page.

    Stops early when the call's time budget runs out and says so in ``stopped_early``.

    Args:
        call (Call): The tool call.
        body (dict[str, Any]): /articles body.
        max_pages (int): Most pages to fetch.

    Returns:
        dict[str, Any]: ``results``, ``total``, ``calls``, ``window_from``, ``window_to``, ``stopped_early``.
    """
    results: list[dict[str, Any]] = []
    total = calls = 0
    page = pages = 1
    window_to = window_from = None
    stopped_early = False
    while page <= pages:
        if page > 1 and call.time_left() <= 0:
            stopped_early = True
            break
        req = {**body, "page": page, "page_size": 100, **({"to_date": window_to} if window_to else {})}
        data = await post_articles(call, req)
        calls += 1
        total = int(data.get("total_hits") or 0)
        window = data.get("window") or {}
        window_to = window_to or window.get("to")
        window_from = window_from or window.get("from")
        pages = min(int(data.get("total_pages") or 1), max_pages, 10)
        results.extend(data.get("results") or [])
        await call.progress(page, pages, f"page {page}/{pages}: {len(results)} articles")
        page += 1
    return {
        "results": results,
        "total": total,
        "calls": calls,
        "window_from": window_from,
        "window_to": window_to,
        "stopped_early": stopped_early,
    }


_NOT_PERSON = re.compile(
    r"\b(staff|admin|editor|editorial|desk|team|news|newswire|wire|press|provided|media|agency|reuters|afp|associated|"
    r"bloomberg|dpa|pti|ians|bureau|correspondent|contributor|club|chronicle|times|post|herald|journal|gazette|daily|"
    r"tribune|online|magazine|redaktion|redacci[oó]n|r[eé]daction)\b",
    re.IGNORECASE,
)


def _tally_key(dim: str, r: dict[str, Any]) -> str | None:
    """The value of one article for a tally dimension (None to leave it out).

    Args:
        dim (str): source, author, country or language.
        r (dict[str, Any]): Article.

    Returns:
        str | None: The value.
    """
    source = r.get("source") or {}
    if dim == "source":
        return source.get("domain") or source.get("name")
    if dim == "author":
        # Bylines that are not people (agencies, desks, "Staff") are left out of author tallies.
        au = str(r.get("author") or "").strip()
        words = au.split()
        if not au or len(au) > 60 or len(words) < 2 or len(words) > 5 or _NOT_PERSON.search(au):
            return None
        return au
    return r.get("country") if dim == "country" else r.get("language")


async def tally_articles(call: Call, query: str, dims_in: list[str], tally_pages: int, body: dict[str, Any]) -> str:
    """Count the fetched articles by outlet, author, country and/or language in one pass.

    Args:
        call (Call): The tool call.
        query (str): The query (for the header).
        dims_in (list[str]): Dimensions to count.
        tally_pages (int): Pages of 100 to fetch.
        body (dict[str, Any]): /articles body.

    Returns:
        str: The tallies.
    """
    got = await fetch_all(call, body, tally_pages)
    results, total = got["results"], got["total"]
    dims = list(dict.fromkeys(dims_in))
    head = (
        f"{query} · {num(total)} matching · {when(got['window_from'])} → {when(got['window_to'])} · tallied the "
        f"{num(len(results))} newest"
        + (" (a sample: raise tally_pages, up to 10, or narrow the window)" if total > len(results) else " (all of them)")
    )
    if got["stopped_early"]:
        head += f" · stopped paging at the server's {call.config.max_call_seconds} s time limit"
    sections: list[str] = []
    for dim in dims:
        groups: dict[str, dict[str, Any]] = {}
        for r in results:
            k = _tally_key(dim, r)
            if not k:
                continue
            g = groups.setdefault(k, {"n": 0, "latest": r, "outlets": []})
            g["n"] += 1
            if str(r.get("published_at")) > str(g["latest"].get("published_at")):
                g["latest"] = r
            domain = (r.get("source") or {}).get("domain")
            if domain and domain not in g["outlets"]:
                g["outlets"].append(domain)
        counted = sum(g["n"] for g in groups.values())
        with_latest = dim in ("source", "author")
        limit = 30 if len(dims) == 1 else 15 if with_latest else 10
        top = sorted(groups.items(), key=lambda kv: -kv[1]["n"])[:limit]
        title = f"By {dim}: {plural(len(groups), 'distinct value')}" + (" (person bylines only)" if dim == "author" else "")
        if not top:
            sections.append(f"{title}\nNone in these articles.")
            continue
        lines: list[str] = []
        for i, (k, g) in enumerate(top):
            share = f"{round(100 * g['n'] / counted)}%"
            if not with_latest:
                lines.append(f"{i + 1}. {k} · {g['n']} ({share})")
                continue
            extra = f" · {', '.join(g['outlets'][:2])}" if dim == "author" else ""
            latest = g["latest"]
            lines.append(
                f"{i + 1}. {k} · {g['n']} ({share}){extra} · latest {when(latest.get('published_at'))}: "
                f"{clip(latest.get('title'), 110)}\n   {latest.get('url')}"
            )
        shown = f" (top {len(top)} shown)" if len(groups) > len(top) else ""
        sections.append(f"{title}{shown}\n" + "\n".join(lines))
    return f"{head}\n" + "\n".join(sections) + f"\n{plural(got['calls'], 'call')} × 5 credits."


def render_search(d: dict[str, Any], query: str) -> str:
    """Render search_news results.

    Args:
        d (dict[str, Any]): /search response.
        query (str): The query.

    Returns:
        str: The text.
    """
    w = d.get("window") or {}
    head = (
        f'"{query}" · effort {d.get("effort")} · '
        + ("newest first · " if d.get("sort_by") and d.get("sort_by") != "relevancy" else "")
        + f"last {w.get('search_window') or '7d'} ({when(w.get('from'))} → {when(w.get('to'))})"
        + f" · {plural(int(d.get('count') or 0), 'result')}"
        + (f" · excluded: {', '.join(d['excluded'])}" if d.get("excluded") else "")
        + (" · window cut to the plan's history" if w.get("clamped") else "")
    )
    results = d.get("results") or []
    if not results:
        return f"{head}\nNo matching news. Try a wider window, fewer filters, other words, or list_articles for exact keyword matching."
    items: list[str] = []
    for i, r in enumerate(results):
        title = _title(r)
        source = r.get("source") or {}
        story = r.get("story") or {}
        meta = " · ".join(
            x
            for x in [
                source.get("name") or source.get("domain"),
                when(r.get("published_at")),
                "/".join(x for x in [r.get("country"), r.get("language")] if x),
                r.get("content_type") if r.get("content_type") not in (None, "", "news_report", "news") else "",
                f"story {story['id']} ({plural(int(story.get('newsrooms') or 1), 'newsroom')})" if story.get("id") else "",
            ]
            if x
        )
        gist = r.get("summary_en") or r.get("summary") or r.get("snippet")
        items.append(f"{i + 1}. {title}\n   {meta}" + (f"\n   {clip(gist, 300)}" if gist else "") + f"\n   {r.get('url')}")
    return f"{head}\n" + "\n".join(items)


def _title(r: dict[str, Any]) -> str:
    """Title with the English translation when it differs.

    Args:
        r (dict[str, Any]): Article.

    Returns:
        str: The title text.
    """
    if r.get("title_en") and r.get("title_en") != r.get("title"):
        return f"{clip(r.get('title'), 140)} [EN: {clip(r['title_en'], 140)}]"
    return clip(r.get("title"), 180)


def render_articles(d: dict[str, Any], count_only: bool) -> str:
    """Render a list_articles page.

    Args:
        d (dict[str, Any]): /articles response.
        count_only (bool): Only the count.

    Returns:
        str: The text.
    """
    w = d.get("window") or {}
    total = int(d.get("total_hits") or 0)
    head = f"{d.get('query')} · {num(total)} matching articles (exact) · {when(w.get('from'))} → {when(w.get('to'))}" + (
        " (start cut to the plan's history)" if w.get("clamped") else ""
    )
    if count_only:
        return head
    results = d.get("results") or []
    if not results:
        return f"{head}\nNo articles on this page."
    page = int(d.get("page") or 1)
    page_size = int(d.get("page_size") or len(results) or 1)
    reachable = min(total, 1000)
    pages = int(d.get("total_pages") or -(-reachable // page_size))
    items: list[str] = []
    for i, r in enumerate(results):
        n = (page - 1) * page_size + i + 1
        source = r.get("source") or {}
        rank = r.get("rank")
        meta = " · ".join(
            x
            for x in [
                source.get("name") or source.get("domain"),
                f"rank {rank}" if rank and rank < 999999 else "",
                when(r.get("published_at")),
                "/".join(x for x in [r.get("country"), r.get("language")] if x),
                f"by {clip(r['author'], 40)}" if r.get("author") else "",
            ]
            if x
        )
        items.append(
            f"{n}. {_title(r)}\n   {meta}" + (f"\n   {clip(r['snippet'], 220)}" if r.get("snippet") else "") + f"\n   {r.get('url')}"
        )
    if page < pages:
        nxt = f'\nPage {page}/{pages}. Next: same call with page={page + 1} and to="{w.get("to")}".' + (
            " Only the first 1,000 matches can be paged; narrow the window for the rest." if total > 1000 else ""
        )
    else:
        nxt = f"\nPage {page}/{pages} (last)."
    return f"{head}\n" + "\n".join(items) + nxt


_WINDOW = re.compile(r"^(\d+)\s*(m|min|minutes?|h|hours?|d|days?|w|weeks?|mo|months?|y|years?)$")


def clamp_window(w: str | None) -> tuple[str | None, str | None]:
    """search_news covers the last 30 days: cut longer windows instead of failing, and say so.

    Args:
        w (str | None): The window as given.

    Returns:
        tuple[str | None, str | None]: The window to send and a note when it was cut.
    """
    if not w:
        return None, None
    m = _WINDOW.match(w.strip().lower())
    if not m:
        return w, None
    n, u = int(m.group(1)), m.group(2)
    if u.startswith("mo"):
        days = n * 30
    elif u.startswith("y"):
        days = n * 365
    elif u.startswith("w"):
        days = n * 7
    elif u.startswith("d"):
        days = n
    else:
        days = 0
    if days > 30:
        return "30d", f'Window "{w}" cut to the last 30 days, the most search_news covers; for older news use list_articles with from/to.'
    return w, None


_REL = re.compile(r"^(\d+)\s*(d|day|days|h|hour|hours|w|week|weeks)(\s+ago)?$")
_DATE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})(?:[t ](\d{2}):(\d{2})(?::(\d{2}))?)?")


def parse_day(s: str, end_of_day: bool = False, now: datetime | None = None) -> datetime | None:
    """Parse ISO dates and the relative forms models send (``7d``, ``7 days ago``, ``12h``, ``today``, ``yesterday``).

    Args:
        s (str): The date.
        end_of_day (bool): For an end date: a bare day means the end of that day.
        now (datetime | None): Current time (tests).

    Returns:
        datetime | None: UTC datetime, or None when unparseable.
    """
    now = now or datetime.now(timezone.utc)
    t = s.strip().lower()
    rel = _REL.match(t)
    if rel:
        n, unit = int(rel.group(1)), rel.group(2)[0]
        delta = timedelta(hours=n) if unit == "h" else timedelta(weeks=n) if unit == "w" else timedelta(days=n)
        d = now - delta
        if unit == "h":
            return d
        return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
    if t == "now":
        return now
    if t in ("today", "yesterday"):
        if end_of_day and t == "today":
            return now
        d = datetime(now.year, now.month, now.day, tzinfo=timezone.utc) - timedelta(days=1 if t == "yesterday" else 0)
        return d + timedelta(days=1) if end_of_day else d
    m = _DATE.match(t)
    if not m:
        return None
    try:
        y, mo, da = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if m.group(4):
            return datetime(y, mo, da, int(m.group(4)), int(m.group(5)), int(m.group(6) or 0), tzinfo=timezone.utc)
        d = datetime(y, mo, da, tzinfo=timezone.utc)
    except ValueError:
        return None
    return d + timedelta(days=1) if end_of_day else d


def _add_month(d: datetime) -> datetime:
    """The same day next month (clamped to the month's last day).

    Args:
        d (datetime): A date.

    Returns:
        datetime: One month later.
    """
    year, month = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    for day in (d.day, 30, 29, 28):
        try:
            return d.replace(year=year, month=month, day=day)
        except ValueError:
            continue
    raise ValueError("unreachable")


def make_buckets(start: datetime, end: datetime, interval: str) -> list[dict[str, Any]]:
    """Split a period into day, week or month buckets; the last one may be partial.

    Args:
        start (datetime): Start (UTC).
        end (datetime): End (UTC).
        interval (str): day, week or month.

    Returns:
        list[dict[str, Any]]: ``{"from", "to", "label", "partial"}`` per bucket.
    """
    out: list[dict[str, Any]] = []
    cur = start
    while cur < end and len(out) < 400:
        if interval == "day":
            nxt = cur + timedelta(days=1)
        elif interval == "week":
            nxt = cur + timedelta(days=7)
        else:
            nxt = _add_month(cur)
        label = cur.strftime("%Y-%m") if interval == "month" else cur.strftime("%Y-%m-%d")
        out.append({"from": cur, "to": min(nxt, end), "label": label, "partial": nxt > end})
        cur = nxt
    return out


def iso(d: datetime) -> str:
    """ISO 8601 with milliseconds and Z, as the API examples use.

    Args:
        d (datetime): UTC datetime.

    Returns:
        str: e.g. ``"2026-11-01T00:00:00.000Z"``.
    """
    return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + f"{d.microsecond // 1000:03d}Z"


def _ts(value: str) -> float:
    """Sortable timestamp of an ISO string (unparseable sorts last).

    Args:
        value (str): ISO timestamp.

    Returns:
        float: Seconds since the epoch.
    """
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return float("inf")
