"""Research agent tools: start_research, get_research, cancel_research."""

import asyncio
import math
import re
import time
from typing import Annotated, Any, Literal
from urllib.parse import quote

from fastmcp import FastMCP
from pydantic import BeforeValidator, Field

from src.config import Config
from src.formatting import clip, num, plural, table, to_json, when
from src.lenient import JsonText, TokenList
from src.tools.common import Call, UserError, register
from src.tools.params import CompanyItem, Schedule, drop_none, items, schedule_body, schedule_text, to_company_in

TERMINAL = {"succeeded", "failed", "cancelled"}

ETA = {
    "fast": "Fast runs usually finish in 3–10 minutes",
    "standard": "Standard runs take 10–30 minutes",
    "max": "Max runs take 15–40 minutes",
    "companies": "company runs take ~2–4 minutes per 6 companies",
}

# PAYG list prices in credits, approved Oct 15 2026; company monitors raised to 3,000 credits a company a month on
# Nov 2. Used only for dry-run estimates. Enterprise plans can differ. Change them here if pricing changes.
PRICES: dict[str, Any] = {
    "run": {"fast": 1000, "standard": 3000, "max": 6000},
    # Each 50 rows delivered past the first 50.
    "extra50": {"fast": 500, "standard": 1500, "max": 3000},
    "per_company": 500,
    "company_monitor_per_month": 3000,
}


def credits(n: int) -> str:
    """``"6,000 credits"``. Prices are always given in credits, never in currency.

    Args:
        n (int): Credits.

    Returns:
        str: The phrase.
    """
    return f"{num(n)} credits"


# Words that pin a time window: dates, months, years, relative periods.
_WINDOW_RE = re.compile(
    r"\b(19|20)\d{2}\b|\b(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\b|"
    r"\b(today|yesterday|tonight|week|weekly|month|monthly|quarter|year|days?|hours?|since|past|last|recent(ly)?|latest|"
    r"this|q[1-4]|h[12]|ytd)\b|\d{4}-\d{2}",
    re.IGNORECASE,
)
# Asking for articles instead of events: the agent should be told what happened, not to collect coverage.
_COVERAGE_RE = re.compile(
    r"\b(news|articles?|stories|coverage|press|headlines|reports?|mentions)\s+(about|on|of|covering|regarding|mentioning)\b|"
    r"\b(find|search|get|list|collect|gather)\s+(all\s+)?(the\s+)?(news|articles?|stories|coverage)\b|"
    r"\b(media|press|news)\s+coverage\b",
    re.IGNORECASE,
)


def query_tips(query: str | None, kind: str) -> list[str]:
    """Free checks on a research query before a paid run; each tip says how to fix it.

    Args:
        query (str | None): The query.
        kind (str): events or companies.

    Returns:
        list[str]: Tips (empty when the query looks fine).
    """
    q = (query or "").strip()
    tips: list[str] = []
    if kind == "events":
        if not _WINDOW_RE.search(q):
            tips.append('No time window: add one, e.g. "since October 1, 2026" or "in the last 30 days"; otherwise the agent picks its own.')
        if _COVERAGE_RE.search(q):
            tips.append(
                'Describe the events, not the coverage: "layoffs at US tech companies in October 2026" works better than '
                '"news articles about tech layoffs".'
            )
        if len(q.split()) < 4:
            tips.append("Very short: say what happened, to whom, where and when (2–4 specifics).")
    elif q and _COVERAGE_RE.search(q):
        tips.append('The filter should name kinds of news, e.g. "funding, acquisitions and leadership changes"; leave it blank for every story.')
    return tips


def events_max(mode: str, rows: int | None = 50) -> int:
    """Most an events run can cost at list price.

    Args:
        mode (str): fast, standard or max.
        rows (int | None): max_rows.

    Returns:
        int: Credits.
    """
    rows = rows or 50
    return PRICES["run"][mode] + PRICES["extra50"][mode] * max(0, math.ceil((rows - 50) / 50))


def estimate(kind: str, mode: str, rows: int | None, companies: int, keep_updated: bool | Schedule | None) -> list[str]:
    """List-price estimate for a run and the monitor it may turn into.

    Args:
        kind (str): events or companies.
        mode (str): Events mode.
        rows (int | None): max_rows.
        companies (int): Number of companies.
        keep_updated (bool | Schedule | None): The keep_updated argument.

    Returns:
        list[str]: Lines.
    """
    out: list[str] = []
    if kind == "events":
        rows = rows or 50
        if rows > 50:
            out.append(
                f"Cost at list price: {credits(PRICES['run'][mode])} including the first 50 rows, "
                f"{credits(PRICES['extra50'][mode])} per further 50 delivered, so at most {credits(events_max(mode, rows))}. "
                "Empty or failed runs are free."
            )
        else:
            out.append(f"Cost at list price: {credits(PRICES['run'][mode])}. Empty or failed runs are free.")
        if keep_updated:
            every = keep_updated.every if isinstance(keep_updated, Schedule) else ("day" if mode == "fast" else "week")
            per_run = PRICES["run"][mode] if every == "week" else round(PRICES["run"][mode] / 2)
            label = "weekly" if every == "week" else "hourly" if every == "hours" else "daily"
            out.append(f"Keep updated: a {label} monitor, {credits(per_run)} per run that finds new rows; runs with nothing new are free.")
    else:
        out.append(
            f"Cost at list price: {credits(PRICES['per_company'])} per company, {credits(PRICES['per_company'] * companies)} "
            f"for {plural(companies, 'company', 'companies')}. Failed runs are free."
        )
        if keep_updated:
            out.append(
                f"Keep updated: a company monitor at {credits(PRICES['company_monitor_per_month'])} per company per month, "
                f"{credits(PRICES['company_monitor_per_month'] * companies)} a month for all of them."
            )
    return out


def _round_rows(v: object) -> object:
    """The API takes 50, 100, 150 or 200 rows: round other numbers up to the next allowed size.

    Args:
        v (object): Raw input.

    Returns:
        object: The allowed size, or the input when it is not a number.
    """
    if isinstance(v, str) and v.strip().isdigit():
        v = int(v.strip())
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return next((x for x in (50, 100, 150, 200) if x >= v), 200)
    return v


MaxRows = Annotated[
    Literal[50, 100, 150, 200] | None,
    BeforeValidator(_round_rows),
    Field(description="Events only: rows to return at most (default 50; plans cap it, e.g. 100). Charged per 50 rows past the first 50."),
]


def register_research_tools(mcp: FastMCP, config: Config) -> None:
    """Register the research toolset.

    Args:
        mcp (FastMCP): The server.
        config (Config): Server settings.
    """

    # ------------------------------------------------------------------ start_research
    @register(
        mcp,
        config,
        name="start_research",
        title="Start a research run",
        description=(
            "Start the NewsCatcher research agent: it searches the news, checks each event against its sources and returns "
            "a verified table (one row per event, with source links). Runs take minutes and cost credits, so use it for "
            "datasets, not quick lookups (use search_news for those). "
            'Two kinds: (1) events: give a query describing what happened, e.g. "layoffs at US tech companies in October 2026" → '
            "rows like company, date, headcount, source_url; columns are chosen for the question. "
            "(2) companies: give companies (domains) or a company_list_id → every recent story about each company "
            "(funding, M&A, leadership, product, legal…), optionally filtered by query. "
            "keep_updated turns it into a monitor. dry_run=true checks the query and shows time and cost first, free. "
            "Returns a run_id; follow it with get_research."
        ),
        toolset="research",
        api="agent",
        annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False},
    )
    async def start_research(
        call: Call,
        query: Annotated[
            str | None,
            Field(
                max_length=2000,
                description=(
                    'Events: the dataset you want in plain words, with the time window, e.g. "Bank M&A deals announced in the '
                    'US since October 1, 2026" or "Series A rounds by fintech startups in Europe this month". '
                    'With companies: optional filter on their news, e.g. "funding, acquisitions and leadership changes" '
                    "(blank = every story)."
                ),
            ),
        ] = None,
        companies: Annotated[
            items(CompanyItem, max_length=500) | None,  # type: ignore[operator]
            TokenList,
            Field(
                description=(
                    'Research these companies\' news instead of an events query: domains like ["stripe.com","wise.com"] '
                    "(up to 50 per run on self-serve plans)."
                ),
            ),
        ] = None,
        company_list_id: Annotated[
            str | None, Field(description="A saved company list (from save_company_list) instead of typing companies.")
        ] = None,
        save_as_list: Annotated[bool, Field(description="Also save the typed companies as a reusable list (its id comes back).")] = False,
        list_name: Annotated[str | None, Field(description="Name for the saved list.")] = None,
        mode: Annotated[
            Literal["fast", "standard", "max"],
            Field(
                description=(
                    "Events only. fast (default): one agent, 3–10 minutes, cheapest. standard: deep research, each row "
                    "checked against its sources, with a cited briefing (10–30 min). max: strongest models, highest recall and cost."
                )
            ),
        ] = "fast",
        max_rows: MaxRows = None,
        lookback_days: Annotated[int | None, Field(ge=1, le=365, description="Companies only: days of news to cover (default 30).")] = None,
        include_market_activity: Annotated[
            bool | None, Field(description="Companies only: keep stock moves and analyst ratings (default true).")
        ] = None,
        keep_updated: Annotated[
            bool | Schedule | None,
            JsonText,
            Field(
                description=(
                    "Turn the run into a monitor once it succeeds: true for the default schedule (daily 09:00 UTC; weekly "
                    "for standard/max events), or a schedule object. The monitor then delivers only what is new."
                )
            ),
        ] = None,
        wait_seconds: Annotated[
            int,
            Field(
                ge=0,
                le=300,
                description=(
                    "Wait up to this many seconds for the run to finish and return its results (default 0: return the "
                    "run_id at once; then call get_research)."
                ),
            ),
        ] = 0,
        dry_run: Annotated[
            bool,
            Field(
                description=(
                    "Check the request without starting it: what would run, how long it takes, the list-price cost, your "
                    "credit balance and tips on the query. Free; nothing is started or charged."
                )
            ),
        ] = False,
    ) -> str:
        """Start an events or companies research run."""
        with_companies = bool(companies or company_list_id)
        if not with_companies and not (query or "").strip():
            raise UserError("Give a query (events) or companies / company_list_id (company news).")
        body: dict[str, Any] = {"query": (query or "").strip() or None}
        if with_companies:
            body["companies"] = (
                {"list_id": company_list_id}
                if company_list_id
                else drop_none({"items": to_company_in(companies or []), "save_as_list": save_as_list or None, "list_name": list_name})
            )
            body["lookback_days"] = lookback_days
            body["include_market_activity"] = include_market_activity
        else:
            body["mode"] = mode
            body["max_rows"] = max_rows
        if keep_updated:
            body["keep_updated"] = {} if keep_updated is True else {"schedule": schedule_body(keep_updated)}  # type: ignore[arg-type]
        if dry_run:
            return await _dry_run(call, query, companies, company_list_id, mode, max_rows, lookback_days, keep_updated, with_companies)
        data = await call.client.post("agent", "/runs", drop_none(body))
        kind = data.get("kind") or ("companies" if with_companies else "events")
        if data.get("batch_id"):
            ident = f"batch {data['batch_id']} ({plural(len(data.get('run_ids') or []), 'run')})"
        else:
            ident = f"run {data.get('run_id')}"
        head = (
            f"Started {kind} research: {ident} (status {data.get('status')})."
            + (f" Saved company list {data['list_id']}." if data.get("list_id") else "")
            + (" A monitor will be created when it succeeds." if data.get("keep_updated") else "")
        )
        ref = {"batch_id": data["batch_id"]} if data.get("batch_id") else {"run_id": data.get("run_id")}
        wait = call.wait_budget(wait_seconds)
        if wait_seconds > 0 and wait > 0:
            detail = await wait_for_run(call, ref, wait)
            return f"{head}\n{render_run(detail, 0, 25)}"
        eta = ETA["companies"] if kind == "companies" else ETA.get(mode, "")
        ref_arg = f'batch_id="{data["batch_id"]}"' if data.get("batch_id") else f'run_id="{data.get("run_id")}"'
        return f"{head}\n{eta}. Next: get_research({ref_arg}, wait_seconds=120) to wait for the results."

    async def _dry_run(
        call: Call,
        query: str | None,
        companies: list[Any] | None,
        company_list_id: str | None,
        mode: str,
        max_rows: int | None,
        lookback_days: int | None,
        keep_updated: bool | Schedule | None,
        with_companies: bool,
    ) -> str:
        """Everything start_research would do, without doing it. The reads it makes (list size, balance) are free.

        Args:
            call (Call): The tool call.
            query (str | None): The query.
            companies (list[Any] | None): Typed companies.
            company_list_id (str | None): A saved list.
            mode (str): Events mode.
            max_rows (int | None): Events rows.
            lookback_days (int | None): Companies window.
            keep_updated (bool | Schedule | None): Monitor request.
            with_companies (bool): Whether it is a companies run.

        Returns:
            str: The report.
        """
        kind = "companies" if with_companies else "events"
        n_companies = len(companies or [])
        if company_list_id:
            data = await call.client.get("agent", f"/companies/lists/{quote(company_list_id, safe='')}")
            n_companies = int((data or {}).get("count") or len((data or {}).get("companies") or []))
        balance: float | None = None
        try:
            sub = await call.client.get("news", "/subscription")
            balance = float(sub.get("credits_balance"))
        except Exception:  # noqa: BLE001 - the estimate still helps without the balance
            balance = None
        if kind == "events":
            what = f'events research, mode {mode}, up to {max_rows or 50} rows: "{clip(query or "", 300)}"'
        else:
            what = (
                f"company news for {plural(n_companies, 'company', 'companies')}"
                + (f" (list {company_list_id})" if company_list_id else "")
                + f", last {lookback_days or 30} days"
                + (f', only "{clip(query, 200)}"' if (query or "").strip() else ", every story")
                + ("; more than 50 companies run as a batch of several runs" if n_companies > 50 else "")
            )
        cost_max = events_max(mode, max_rows) if kind == "events" else PRICES["per_company"] * n_companies
        tips = query_tips(query, kind)
        lines = [
            "Dry run: nothing was started or charged.",
            f"Would start: {what}.",
            f"Time: {ETA['companies'] if kind == 'companies' else ETA[mode]}.",
            *estimate(kind, mode, max_rows, n_companies, keep_updated),
            (
                f"Balance: {num(balance)} credits"
                + (" (not enough for this run: top up or pick a smaller option)" if balance < cost_max else "")
                + "."
            )
            if balance is not None and math.isfinite(balance)
            else "",
            "Enterprise plans can be priced differently; get_account shows the balance after the run.",
            ("Query check:\n" + "\n".join(f"- {t}" for t in tips)) if tips else "Query check: no issues found.",
            "To run it: the same start_research call without dry_run.",
        ]
        return "\n".join(x for x in lines if x)

    # ------------------------------------------------------------------ get_research
    @register(
        mcp,
        config,
        name="get_research",
        title="Get research results",
        description=(
            "Status and results of a research run from start_research: waits (up to wait_seconds) while it runs, then "
            "returns the table (columns + rows with source links), each company's coverage for company runs, and the cited "
            "briefing for Standard/Max runs. "
            "Call it with no run_id to list your recent runs (ids, status, titles). Free."
        ),
        toolset="research",
        api="agent",
        annotations={"readOnlyHint": True, "idempotentHint": True},
    )
    async def get_research(
        call: Call,
        run_id: Annotated[str | None, Field(description="The run to read. Leave out (and batch_id too) to list your recent runs.")] = None,
        batch_id: Annotated[
            str | None, Field(description="A batch (a company list split over several runs) instead of a run.")
        ] = None,
        wait_seconds: Annotated[
            int,
            Field(
                ge=0,
                le=300,
                description=(
                    "If the run is still going, wait up to this many seconds for it to finish (default 30; use 120–300 for "
                    "long runs; 0 = status now)."
                ),
            ),
        ] = 30,
        rows_offset: Annotated[int, Field(ge=0, description="First row to show (for paging through a big table).")] = 0,
        rows_limit: Annotated[int, Field(ge=0, le=200, description="Rows to show (default 25, max 200). Page with rows_offset.")] = 25,
        exclude_rows: Annotated[
            items(Annotated[int, Field(ge=1)], max_length=500) | None,  # type: ignore[operator]
            JsonText,
            Field(
                description=(
                    "Row numbers (#) to leave out after checking (duplicates, out of scope): the table and the counts "
                    "line then cover only the kept rows."
                )
            ),
        ] = None,
        sort: Annotated[
            Literal["original", "newest", "oldest", "importance"],
            Field(
                description=(
                    "Row order: original (as the run returned them), newest or oldest first by the row's date column, or "
                    "importance (most important first, then newest). Row numbers (#) stay the run's own."
                )
            ),
        ] = "original",
        kind: Annotated[Literal["events", "companies"] | None, Field(description="When listing: only runs of this kind.")] = None,
        limit: Annotated[int, Field(ge=1, le=100, description="When listing: how many recent runs.")] = 10,
        format: Annotated[Literal["text", "json"], Field(description="text (default) or json.")] = "text",
    ) -> str:
        """Wait for a run and show its table, or list recent runs."""
        if not run_id and not batch_id:
            data = await call.client.get("agent", "/runs", {"limit": limit, "kind": kind})
            if format == "json":
                return to_json(data)
            runs = (data or {}).get("runs") or []
            if not runs:
                return "No research runs yet. Start one with start_research."
            return f"Your last {plural(len(runs), 'run')} (newest first):\n" + "\n".join(
                f"- {r.get('run_id')} · {r.get('kind')} · {r.get('mode')} · {r.get('status')} · {when(r.get('created_at'))} · "
                f"{clip(r.get('title') or r.get('query'), 120)}"
                + (f" · monitor {r['monitor_id']}" if r.get("monitor_id") else "")
                + (f" · batch {r['batch_id']}" if r.get("batch_id") else "")
                for r in runs
            )
        ref = {"batch_id": batch_id} if batch_id else {"run_id": run_id}
        detail = sort_rows(drop_rows(await wait_for_run(call, ref, call.wait_budget(wait_seconds)), exclude_rows), sort)
        if format == "json":
            rows = [
                ({"#": r["__n"], **{k: v for k, v in r.items() if k != "__n"}} if r.get("__n") else r)
                for r in (detail.get("rows") or [])[rows_offset : rows_offset + rows_limit]
            ]
            return to_json({**detail, "rows": rows, "rows_total": len(detail.get("rows") or []), "rows_offset": rows_offset})
        return render_run(detail, rows_offset, rows_limit)

    # ------------------------------------------------------------------ cancel_research
    @register(
        mcp,
        config,
        name="cancel_research",
        title="Cancel a research run",
        description=(
            "Stop a queued or running research run (or batch). A cancelled run is not charged. Use when the user asks to "
            "stop, or a run was started by mistake."
        ),
        toolset="research",
        api="agent",
        annotations={"readOnlyHint": False, "destructiveHint": True, "idempotentHint": True},
    )
    async def cancel_research(
        call: Call,
        run_id: Annotated[str | None, Field(description="The run to cancel.")] = None,
        batch_id: Annotated[str | None, Field(description="Or the batch to cancel.")] = None,
    ) -> str:
        """Cancel a run or batch."""
        if not run_id and not batch_id:
            raise UserError("Give run_id or batch_id.")
        path = f"/batches/{quote(batch_id, safe='')}/cancel" if batch_id else f"/runs/{quote(run_id or '', safe='')}/cancel"
        data = await call.client.post("agent", path, {}, idempotent=True)
        target = f"batch {batch_id}" if batch_id else f"run {run_id}"
        return f"Cancel requested: {target} → {(data or {}).get('status') or 'cancelling'}."


async def wait_for_run(call: Call, ref: dict[str, Any], wait_seconds: float) -> dict[str, Any]:
    """Poll a run (or batch) until it ends or the wait runs out, reporting each phase as progress.

    Args:
        call (Call): The tool call.
        ref (dict[str, Any]): ``{"run_id": ...}`` or ``{"batch_id": ...}``.
        wait_seconds (float): Longest wait.

    Returns:
        dict[str, Any]: The last run detail.
    """
    if ref.get("batch_id"):
        path = f"/batches/{quote(ref['batch_id'], safe='')}"
    else:
        path = f"/runs/{quote(ref['run_id'], safe='')}"
    deadline = time.monotonic() + wait_seconds
    polls = 0
    while True:
        data = await call.client.get("agent", path)
        status = data.get("status")
        if status in TERMINAL or time.monotonic() >= deadline:
            return data
        polls += 1
        phases = data.get("phases") or []
        active = next((p for p in phases if p.get("status") == "active"), None)
        done = sum(1 for p in phases if p.get("status") == "done")
        bp = data.get("progress")
        if bp and bp.get("companies_total"):
            await call.progress(bp.get("companies_done") or 0, bp["companies_total"], f"{status}: {batch_text(bp)}")
        else:
            await call.progress(done, len(phases) or None, f"{status}" + (f": {active.get('label')}" if active else ""))
        remaining = deadline - time.monotonic()
        await asyncio.sleep(max(0.0, min(5.0 if polls < 3 else 10.0, remaining)))


def batch_text(p: dict[str, Any]) -> str:
    """Batch progress in words.

    Args:
        p (dict[str, Any]): Batch progress.

    Returns:
        str: e.g. ``"20/60 companies, 1/3 runs done"``.
    """
    return (
        f"{p.get('companies_done') or 0}/{p.get('companies_total') or '?'} companies, "
        f"{p.get('runs_done') or 0}/{p.get('runs_total') or '?'} runs done"
    )


COMPANY_COLUMNS = ["company", "date", "story_type", "importance", "headline", "summary", "outlets", "url"]
_PHASE_MARK = {"done": "✓", "active": "…", "skipped": "–"}


def render_run(d: dict[str, Any], offset: int, limit: int) -> str:
    """Render a run: status, phases, next steps while running; table, counts and briefing when finished.

    Args:
        d (dict[str, Any]): Run detail.
        offset (int): First row to show.
        limit (int): Rows to show.

    Returns:
        str: The text.
    """
    ident = f"Batch {d.get('batch_id')}" if d.get("batch_id") and not d.get("run_id") else f"Run {d.get('run_id')}"
    phases = d.get("phases") or []
    secs = sum(p.get("seconds") or 0 for p in phases)
    phase_line = " · ".join(
        f"{_PHASE_MARK.get(p.get('status'), '○')} {p.get('label')}" + (f" {p['seconds']}s" if p.get("seconds") else "")
        for p in phases
    )
    status = d.get("status")
    lines = [
        f"{ident} · {d.get('kind') or 'events'}"
        + (f" · {d['mode']}" if d.get("mode") else "")
        + f" · {status}"
        + (f' · "{clip(d.get("title") or d.get("query"), 140)}"' if d.get("title") or d.get("query") else "")
        + (f" · news {d['window_from']} → {d.get('window_to')}" if d.get("window_from") else "")
    ]
    if phase_line:
        lines.append(f"Phases: {phase_line}" + (f" ({round(secs / 60)} min)" if secs and status in TERMINAL else ""))
    if d.get("progress"):
        lines.append(f"Batch progress: {batch_text(d['progress'])}")
    if d.get("error"):
        lines.append(f"Error: {d['error']}")
    if status not in TERMINAL:
        if status == "queued":
            lines.append("Queued: the account runs a few research runs at a time, so this one starts when an earlier run finishes.")
        eta = ETA["companies"] if d.get("kind") == "companies" else ETA.get(d.get("mode") or "", "runs take minutes")
        lines.append(
            f"Still {status}. Call get_research again with wait_seconds=120–300 ({eta}); the table is not ready yet, so "
            "don't build it from other searches meanwhile. The run keeps going if you stop waiting and its results stay "
            "available by run_id: if you have to stop before it ends, tell the user it is still running and to say "
            '"refresh" for the results.'
        )
        return "\n".join(lines)
    if status == "cancelled":
        lines.append("The run was cancelled (not charged).")
        return "\n".join(lines)
    rows: list[dict[str, Any]] = d.get("rows") or []
    companies = d.get("companies")
    if d.get("kind") == "companies" and isinstance(companies, list) and companies:
        cov = [
            f"{c.get('company') or c.get('domain')} ({c.get('domain')}): {c.get('news_status')}"
            + (f", {plural(int(c['stories']), 'story', 'stories')}" if c.get("stories") is not None else "")
            for c in companies
        ]
        lines.append(f"Coverage: {' · '.join(cov[:30])}" + (f" · … {len(cov) - 30} more" if len(cov) > 30 else ""))
    if d.get("report"):
        lines.append(f"Briefing:\n{clip(d['report'], 4000)}")
    if not rows:
        lines.append(
            "No rows: nothing qualified. Rephrase the query, widen the time window, or try mode=standard."
            if status == "succeeded"
            else "No rows."
        )
    else:
        all_cols: list[str] = d.get("columns") or [k for k in rows[0] if k != "__n"]
        if d.get("kind") == "companies":
            columns = [c for c in COMPANY_COLUMNS if c in (d.get("columns") or COMPANY_COLUMNS)]
        else:
            columns = all_cols
        page = rows[offset : offset + limit]
        excluded = d.get("excluded") or []
        kept = f" kept (left out #{', #'.join(str(n) for n in excluded)})" if excluded else ""
        lines.append(f"{plural(len(rows), 'row')}{kept} · columns: {', '.join(all_cols)}")
        summary = summarize_rows(all_cols, rows)
        if summary:
            lines.append(summary)
        # "#" is the run's own row number (kept when sorting).
        if page:
            lines.append(
                table(
                    ["#", *[c for c in columns if c != "__n"]],
                    [{"#": r.get("__n") or offset + i + 1, **r} for i, r in enumerate(page)],
                    140 if d.get("kind") == "companies" else 180,
                )
            )
        shown = f"Rows {offset + 1}–{offset + len(page)} of {len(rows)}." if page else f"No rows at offset {offset}."
        more = f" More: rows_offset={offset + len(page)}." if offset + len(page) < len(rows) else ""
        lines.append(f"{shown}{more}")
    if d.get("keep_updated"):
        k = d["keep_updated"]
        lines.append(
            f"Keep updated: {k.get('status')}"
            + (f", monitor {k['monitor_id']}" if k.get("monitor_id") else "")
            + (f" ({schedule_text(k['schedule'])})" if k.get("schedule") else "")
            + (f": {k['error']}" if k.get("error") else "")
        )
    elif d.get("monitor_id"):
        lines.append(f"Monitor: {d['monitor_id']}")
    if d.get("list_id"):
        lines.append(f"Company list: {d['list_id']}")
    return "\n".join(lines)


def drop_rows(d: dict[str, Any], exclude: list[int] | None) -> dict[str, Any]:
    """Leave out rows by their run row number (#), keeping each kept row's own number; note what was dropped.

    Args:
        d (dict[str, Any]): Run detail.
        exclude (list[int] | None): Row numbers to leave out.

    Returns:
        dict[str, Any]: The detail with the kept rows and ``excluded`` (the sorted row numbers left out).
    """
    rows = d.get("rows") if isinstance(d, dict) else None
    if not exclude or not isinstance(rows, list):
        return d
    drop = set(exclude)
    numbered = [{**r, "__n": r.get("__n") or i + 1} for i, r in enumerate(rows)]
    return {**d, "rows": [r for r in numbered if r["__n"] not in drop], "excluded": sorted(drop)}


def _importance(v: Any) -> float:
    """Importance as a number: 1–5 as given, or low/medium/high.

    Args:
        v (Any): The cell.

    Returns:
        float: The score (0 when missing).
    """
    if v is None or v == "":
        return 0.0
    try:
        return float(v)
    except (TypeError, ValueError):
        return {"high": 3.0, "medium": 2.0, "low": 1.0}.get(str(v).lower(), 0.0)


def sort_rows(d: dict[str, Any], order: str) -> dict[str, Any]:
    """Order rows by their date column (ISO dates sort as text), or by importance then date; undated rows go last.

    Args:
        d (dict[str, Any]): Run detail.
        order (str): original, newest, oldest or importance.

    Returns:
        dict[str, Any]: The detail with sorted rows (each keeps its original number in ``__n``).
    """
    rows = d.get("rows") if isinstance(d, dict) else None
    if order == "original" or not isinstance(rows, list) or len(rows) < 2:
        return d
    cols = d.get("columns") or list(rows[0].keys())
    date_col = next((c for c in cols if re.search("date", c, re.IGNORECASE)), None)
    imp_col = next((c for c in cols if c.lower() == "importance"), None)
    if (order == "importance" and not imp_col) or (order != "importance" and not date_col):
        return d
    numbered = [{**r, "__n": r.get("__n") or i + 1} for i, r in enumerate(rows)]

    def date(r: dict[str, Any]) -> str:
        """The row's date as text ("" when missing)."""
        return str(r.get(date_col) or "") if date_col else ""

    dated = [r for r in numbered if date(r)]
    undated = [r for r in numbered if not date(r)]
    if order == "importance":
        # most important first; within one importance, newest first and undated last
        dated.sort(key=date, reverse=True)
        ordered = sorted(dated + undated, key=lambda r: -_importance(r.get(imp_col)))
        return {**d, "rows": ordered}
    dated.sort(key=date, reverse=order != "oldest")
    return {**d, "rows": dated + undated}


_SKIP = re.compile(
    r"url|link|summary|headline|title|description|details|snippet|evidence|reason|^source$|note|quote|^id$|_id$|^rank$|^origin$",
    re.IGNORECASE,
)
_MULTI = re.compile(r"investor|actor|parties|participants|acquirer|buyer", re.IGNORECASE)
_SPLIT = re.compile(r"\s*[;,]\s*|\s+and\s+")
_BRACKETS = re.compile(r"\s*\([^)]*\)")
_NUMERIC = re.compile(r"^-?\d+(\.\d+)?$")


def _fmt_amount(x: float) -> str:
    """``3000000`` → ``"3M"``, ``2.5e9`` → ``"2.5B"``.

    Args:
        x (float): Amount.

    Returns:
        str: Short form.
    """
    if x >= 1e9:
        return f"{float(f'{x / 1e9:.2f}'):g}B"
    if x >= 1e6:
        return f"{float(f'{x / 1e6:.1f}'):g}M"
    return num(x)


def summarize_rows(columns: list[str], rows: list[dict[str, Any]]) -> str:
    """Counts over every row, so a summary needs no paging: date range, top values of short categorical columns,
    investors in any role, and disclosed amounts per currency.

    Args:
        columns (list[str]): Column names.
        rows (list[dict[str, Any]]): All rows.

    Returns:
        str: One line, or "" when there is nothing worth counting.
    """
    if len(rows) < 2:
        return ""
    has_company = any(re.fullmatch("company", c, re.IGNORECASE) for c in columns)
    parts: list[str] = []
    date_col = next((c for c in columns if re.search("date", c, re.IGNORECASE)), None)
    if date_col:
        ds = sorted(v for v in (str(r.get(date_col) or "") for r in rows) if re.match(r"^\d{4}-\d{2}", v))
        if ds:
            parts.append(f"{date_col} {ds[0][:10]} → {ds[-1][:10]}")
    for c in columns:
        if c == date_col or _SKIP.search(c) or (has_company and re.search("domain", c, re.IGNORECASE)):
            continue
        multi = bool(_MULTI.search(c))
        counts: dict[str, dict[str, Any]] = {}
        filled = 0
        for r in rows:
            raw = r.get(c)
            if raw is None or raw == "" or isinstance(raw, (dict, list)):
                continue
            filled += 1
            # "Qilin (claimed)" and "Qilin" are one actor: drop bracketed notes in name columns, then split lists.
            values = [v for v in _SPLIT.split(_BRACKETS.sub("", str(raw))) if v] if multi else [_scalar(raw)]
            for v in values:
                label = v.strip()
                if not label or len(label) > 60:
                    continue
                e = counts.setdefault(label.lower(), {"label": label, "n": 0})
                e["n"] += 1
        if not filled or not counts:
            continue
        ordered = sorted(counts.values(), key=lambda e: -e["n"])
        repeats = ordered[0]["n"] >= 2
        categorical = len(counts) <= max(8, math.ceil(len(rows) * (1.5 if multi else 0.6)))
        numeric = all(_NUMERIC.match(e["label"]) for e in ordered)
        constant = len(counts) < 2 and filled == len(rows) and not multi
        if not repeats or not categorical or constant or (numeric and len(counts) > 6):
            continue
        top = ", ".join(f"{e['label']} {e['n']}" for e in ordered[:6])
        blank = len(rows) - filled
        parts.append(
            f"{c}: {top}" + (f", +{len(ordered) - 6} more" if len(ordered) > 6 else "") + (f" (blank {blank})" if blank else "")
        )
    inv_cols = [c for c in columns if re.search("investor", c, re.IGNORECASE)]
    if len(inv_cols) > 1:
        inv: dict[str, dict[str, Any]] = {}
        for r in rows:
            names: dict[str, str] = {}
            for c in inv_cols:
                for v in _SPLIT.split(_BRACKETS.sub("", str(r.get(c) or ""))):
                    t = v.strip()
                    if t and len(t) <= 60 and not re.fullmatch(r"none|n/a|undisclosed|not disclosed|unknown", t, re.IGNORECASE):
                        names.setdefault(t.lower(), t)
            for key, t in names.items():
                e = inv.setdefault(key, {"label": t, "n": 0})
                e["n"] += 1
        top_inv = sorted((e for e in inv.values() if e["n"] >= 2), key=lambda e: -e["n"])[:8]
        parts.append(
            "investors in 2+ rows (any role): " + ", ".join(f"{e['label']} {e['n']}" for e in top_inv)
            if top_inv
            else "no investor appears in 2+ rows"
        )
    amount_col = next((c for c in columns if re.search("amount|deal_value|value_usd|size", c, re.IGNORECASE)), None)
    if amount_col:
        cur_col = next((c for c in columns if re.search("currency", c, re.IGNORECASE)), None)
        sums: dict[str, dict[str, float]] = {}
        undisclosed = 0
        for r in rows:
            raw = r.get(amount_col)
            value = _amount(raw)
            if value is None:
                undisclosed += 1
                continue
            cur = (str(r.get(cur_col) or "").strip() or "?") if cur_col else ""
            e = sums.setdefault(cur, {"sum": 0.0, "n": 0})
            e["sum"] += value
            e["n"] += 1
        if sums:
            parts.append(
                f"{amount_col} disclosed: "
                + "; ".join(f"{(c + ' ') if c else ''}{_fmt_amount(e['sum'])} over {plural(int(e['n']), 'row')}" for c, e in sums.items())
                + (f"; {undisclosed} undisclosed or not numeric" if undisclosed else "")
            )
    return f"Counts over all {len(rows)} rows shown in this result (use these for totals; no need to page): {' · '.join(parts)}" if parts else ""


def _scalar(v: Any) -> str:
    """A cell value as text (whole floats without .0).

    Args:
        v (Any): Value.

    Returns:
        str: Text.
    """
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def _amount(raw: Any) -> float | None:
    """A positive number from an amount cell (``"2,000,000"`` works), else None.

    Args:
        raw (Any): Cell value.

    Returns:
        float | None: The amount.
    """
    if raw is None or raw == "" or isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        value = float(raw)
    else:
        try:
            value = float(re.sub(r"[,\s]", "", str(raw)))
        except ValueError:
            return None
    return value if math.isfinite(value) and value > 0 else None
