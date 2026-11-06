"""Monitor tools: create_monitor, get_monitor, get_monitor_updates, update_monitor."""

import asyncio
from typing import Annotated, Any, Literal
from urllib.parse import quote

from fastmcp import FastMCP
from pydantic import Field

from src.config import Config
from src.formatting import clip, plural, table, to_json, when
from src.lenient import JsonText, TokenList
from src.tools.common import Call, UserError, register
from src.tools.params import CompanyItem, Schedule, drop_none, items, schedule_body, schedule_text, to_company_in


def render_monitor(m: dict[str, Any]) -> str:
    """One monitor in one line.

    Args:
        m (dict[str, Any]): Monitor from the API.

    Returns:
        str: The line.
    """
    if m.get("kind") == "dataset":
        dataset = m.get("dataset") or {}
        who = f're-runs "{clip(m.get("query") or dataset.get("topic") or "", 120)}" ({dataset.get("mode") or "fast"})'
    else:
        who = (
            plural(len(m.get("companies") or []), "company", "companies")
            + (f" (follows list {m['list_id']})" if m.get("list_id") else "")
            + (f', watching for "{clip(m["query"], 100)}"' if m.get("query") else ", every story")
        )
    if m.get("enabled"):
        state = f"next run {when(m.get('next_run_at'))}"
    else:
        state = "paused" + (f" ({m['paused_reason']})" if m.get("paused_reason") else "")
    return f"{m.get('monitor_id')} · \"{clip(m.get('name'), 80)}\" · {m.get('kind')} monitor · {who} · {schedule_text(m.get('schedule'))} · {state}"


def story_line(s: dict[str, Any], update: Any = None) -> str:
    """One delivered story.

    Args:
        s (dict[str, Any]): Story.
        update (Any): None when unknown, else whether it is an update to an earlier story.

    Returns:
        str: The lines.
    """
    tag = "" if update is None else "[update] " if update else "[new] "
    importance = s.get("importance") if s.get("importance") is not None else "?"
    outlets = s.get("outlets") if s.get("outlets") is not None else "?"
    return (
        f"- {tag}{s.get('last_date') or s.get('first_date') or ''} · {s.get('domain') or ''} · {s.get('story_type') or ''} · "
        f"importance {importance} · {outlets} outlets · {clip(s.get('headline') or '', 140)}\n"
        f"  {clip(s.get('summary') or '', 200)}\n"
        f"  {(s.get('lead') or {}).get('url') or ''}"
    )


ScheduleArg = Annotated[Schedule | None, JsonText]
Companies500 = items(CompanyItem, max_length=500)


def register_monitor_tools(mcp: FastMCP, config: Config) -> None:
    """Register the monitors toolset.

    Args:
        mcp (FastMCP): The server.
        config (Config): Server settings.
    """

    @register(
        mcp,
        config,
        name="create_monitor",
        title="Create a monitor",
        description=(
            "Watch for new developments on a schedule and get only what is new each run. Three ways: "
            '(1) from_run_id: "monitor this" for a finished research run (an events dataset is re-run for new rows; a '
            "company run becomes a company monitor); "
            "(2) companies or company_list_id: new stories about those companies, optionally only those matching query "
            '(e.g. "funding, M&A, executive changes"); '
            "the default schedule is daily 09:00 UTC. Read deliveries with get_monitor_updates. Monitors are billed per run "
            "or per company (see the pricing docs); empty runs are free."
        ),
        toolset="monitors",
        api="agent",
        annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False},
    )
    async def create_monitor(
        call: Call,
        from_run_id: Annotated[str | None, Field(description="A succeeded research run to keep updated.")] = None,
        companies: Annotated[Companies500 | None, TokenList, Field(description="Companies by domain.")] = None,
        company_list_id: Annotated[
            str | None, Field(description="A saved company list; the monitor follows changes to the list.")
        ] = None,
        query: Annotated[
            str | None,
            Field(description="Company monitors: only stories about this. Dataset monitors: the research request (default: the run's query)."),
        ] = None,
        name: Annotated[str | None, Field(description="Monitor name.")] = None,
        schedule: Annotated[
            ScheduleArg, Field(description="When it runs (default daily at 09:00 UTC; weekly for standard/max datasets).")
        ] = None,
        include_market_activity: Annotated[
            bool | None, Field(description="Company monitors: also stock moves and analyst ratings (default false).")
        ] = None,
        run_now: Annotated[
            bool, Field(description="Also run it right away (within ~5 minutes) instead of waiting for the schedule.")
        ] = False,
    ) -> str:
        """Create a dataset or company monitor."""
        if sum(bool(x) for x in (from_run_id, companies, company_list_id)) != 1:
            raise UserError("Give exactly one of from_run_id, companies or company_list_id.")
        kind = "companies"
        if from_run_id:
            run = await call.client.get("agent", f"/runs/{quote(from_run_id, safe='')}")
            if run.get("status") != "succeeded":
                raise UserError(f"Run {from_run_id} is {run.get('status')}; only a succeeded run can be monitored.")
            kind = "companies" if run.get("kind") == "companies" else "dataset"
        body = drop_none(
            {
                "kind": kind,
                "name": name,
                "from_run_id": from_run_id,
                "companies": to_company_in(companies) if companies else None,
                "list_id": company_list_id,
                "query": query,
                "schedule": schedule_body(schedule),
                "settings": {"include_market_activity": include_market_activity} if include_market_activity is not None else None,
            }
        )
        m = await call.client.post("agent", "/monitors", body)
        tail = ""
        if run_now:
            await call.client.post("agent", f"/monitors/{quote(m['monitor_id'], safe='')}/run", {})
            tail = "\nRunning now (starts within ~5 minutes). Check it with get_monitor_updates."
        return f"Created monitor {render_monitor(m)}{tail}"

    @register(
        mcp,
        config,
        name="get_monitor",
        title="Get monitors",
        description="Show one monitor (settings, schedule, state and its recent runs), or with no monitor_id, all your monitors. Free.",
        toolset="monitors",
        api="agent",
        annotations={"readOnlyHint": True, "idempotentHint": True},
    )
    async def get_monitor(
        call: Call,
        monitor_id: Annotated[str | None, Field(description="The monitor; leave out to list all.")] = None,
        format: Literal["text", "json"] = "text",
    ) -> str:
        """Show one monitor or all monitors."""
        if not monitor_id:
            data = await call.client.get("agent", "/monitors")
            if format == "json":
                return to_json(data)
            ms = (data or {}).get("monitors") or []
            if not ms:
                return "No monitors yet. Create one with create_monitor, or start_research(keep_updated=true)."
            return "\n".join(f"- {render_monitor(m)}" for m in ms)
        mid = quote(monitor_id, safe="")
        m, runs = await asyncio.gather(
            call.client.get("agent", f"/monitors/{mid}"),
            call.client.get("agent", f"/monitors/{mid}/runs", {"limit": 5}),
        )
        if format == "json":
            return to_json({**m, "recent_runs": (runs or {}).get("runs")})
        rs = (runs or {}).get("runs") or []
        cs = m.get("companies") or []
        companies_line = ""
        if cs:
            companies_line = (
                f"Companies: {', '.join(c.get('domain') for c in cs[:40])}" + (f" … +{len(cs) - 40}" if len(cs) > 40 else "") + "\n"
            )
        if rs:
            recent = "Recent runs:\n" + "\n".join(
                f"- {r.get('run_id')} · {r.get('role')} · {r.get('status')} · {when(r.get('finished_at') or r.get('created_at'))}"
                + (f" · {r['error']}" if r.get("error") else "")
                for r in rs
            ) + "\nRead what a run delivered with get_monitor_updates."
        else:
            recent = "No runs yet."
        return f"{render_monitor(m)}\n{companies_line}{recent}"

    @register(
        mcp,
        config,
        name="get_monitor_updates",
        title="Get monitor updates",
        description=(
            "What a monitor delivered: the new (or grown) rows or stories of its latest run, or of a given run_id, each "
            "marked new or update. "
            "For a company monitor, feed=true instead returns the full story feed of its companies over the last `days`. Free."
        ),
        toolset="monitors",
        api="agent",
        annotations={"readOnlyHint": True, "idempotentHint": True},
    )
    async def get_monitor_updates(
        call: Call,
        monitor_id: Annotated[str, Field(description="The monitor.")],
        run_id: Annotated[str | None, Field(description="A specific monitor run (default: the latest).")] = None,
        feed: Annotated[bool, Field(description="Company monitors: every story of the last `days` instead of one run's delivery.")] = False,
        days: Annotated[int, Field(ge=1, le=365, description="With feed=true: days of stories (default 7).")] = 7,
        limit: Annotated[int, Field(ge=1, le=200, description="Rows or stories to show (default 25).")] = 25,
        format: Literal["text", "json"] = "text",
    ) -> str:
        """Deliveries of a monitor run, or a company monitor's feed."""
        mid = quote(monitor_id, safe="")
        if feed:
            m = await call.client.get("agent", f"/monitors/{mid}")
            if m.get("kind") == "dataset":
                data = await call.client.get("agent", f"/monitors/{mid}/rows", {"limit": limit})
                if format == "json":
                    return to_json(data)
                rows = (data or {}).get("rows") or []
                if not rows:
                    return "This dataset monitor has no rows yet."
                cols = [c for c in rows[0] if c not in ("rank", "origin", "related_company")]
                return f"{plural(len(rows), 'row')} delivered so far (newest first), including the source run's rows:\n{table(cols, rows, 140)}"
            data = await call.client.get("agent", f"/monitors/{mid}/stories", {"days": days, "limit": limit})
            if format == "json":
                return to_json(data)
            ss = (data or {}).get("stories") or []
            if not ss:
                return f"No stories in the last {days} days."
            return f"{plural(len(ss), 'story', 'stories')}, newest first:\n" + "\n".join(story_line(s) for s in ss)
        if not run_id:
            runs = await call.client.get("agent", f"/monitors/{mid}/runs", {"limit": 10})
            listed = (runs or {}).get("runs") or []
            # The "source" run is the research run the monitor was made from; its results are read with get_research.
            own = [r for r in listed if r.get("role") != "source"]
            finished = next((r for r in own if r.get("status") == "succeeded"), None)
            if not finished:
                active = next((r for r in own if r.get("status") in ("running", "queued")), None)
                source = next((r for r in listed if r.get("role") == "source"), None)
                m = await call.client.get("agent", f"/monitors/{mid}")
                parts = [
                    f"Monitor run {active.get('run_id')} is {active.get('status')}; check again in a few minutes."
                    if active
                    else "No monitor run has finished yet.",
                    f"Next scheduled run {when(m.get('next_run_at'))}." if m.get("enabled") else "The monitor is paused.",
                    f'Its starting results are in the run it was made from: get_research(run_id="{source.get("run_id")}").'
                    if source
                    else "",
                    "" if active else 'update_monitor(action="run_now") runs it within ~5 minutes.',
                ]
                return " ".join(p for p in parts if p)
            run_id = finished.get("run_id")
        r = await call.client.get("agent", f"/monitors/runs/{quote(str(run_id), safe='')}")
        rows = r.get("rows") or []
        stories = r.get("stories") or []
        if format == "json":
            return to_json({**r, "rows": rows[:limit], "stories": stories[:limit]})
        n = len(rows) or len(stories)
        head = (
            f"Monitor run {r.get('run_id')} · {r.get('status')} · {when(r.get('finished_at') or r.get('created_at'))}"
            + (f" · covers {r['window_from']} → {r.get('window_to')}" if r.get("window_from") else "")
            + f" · {plural(n, 'delivery', 'deliveries')}"
            + (f" (+{r['more']} more next run)" if r.get("more") else "")
        )
        companies = r.get("companies") or []
        cov = ""
        if companies:
            cov = "\nCompanies: " + " · ".join(
                (
                    f"{c.get('domain')} {c.get('news_status') or ''}"
                    + (f" ({c.get('created') or 0} new, {c.get('updated') or 0} updated)" if c.get("created") or c.get("updated") else "")
                ).strip()
                for c in companies[:30]
            )
        if not n:
            return f"{head}{cov}\nNothing new in this run."
        if rows:
            cols = [c for c in (r.get("columns") or list(rows[0].keys())) if c not in ("rank", "origin", "related_company", "domain")]
            return f"{head}{cov}\n{table(cols, rows[:limit], 140)}" + (f"\n… {len(rows) - limit} more (raise limit)." if len(rows) > limit else "")
        return (
            f"{head}{cov}\n"
            + "\n".join(
                story_line({**(x.get("story") or x), "domain": x.get("company") or (x.get("story") or {}).get("domain")}, x.get("update"))
                for x in stories[:limit]
            )
            + (f"\n… {len(stories) - limit} more (raise limit)." if len(stories) > limit else "")
        )

    @register(
        mcp,
        config,
        name="update_monitor",
        title="Update a monitor",
        description=(
            "Change a monitor: pause or resume it, run it now, edit its name, schedule, query or companies, or delete it. "
            "Resume with fill_gap=true (default) to also deliver what it missed while paused (up to 30 days)."
        ),
        toolset="monitors",
        api="agent",
        annotations={"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False},
    )
    async def update_monitor(
        call: Call,
        monitor_id: Annotated[str, Field(description="The monitor.")],
        action: Annotated[
            Literal["edit", "pause", "resume", "run_now", "delete"], Field(description="What to do (default edit).")
        ] = "edit",
        name: str | None = None,
        schedule: Annotated[ScheduleArg, Field(description="New schedule.")] = None,
        query: Annotated[
            str | None,
            Field(description='Company monitors: what to watch for ("" for every story). Dataset monitors: the research request.'),
        ] = None,
        companies: Annotated[
            Companies500 | None,
            TokenList,
            Field(description="Replace its companies (not for monitors that follow a list)."),
        ] = None,
        fill_gap: Annotated[bool, Field(description="With resume: deliver what it missed while paused.")] = True,
    ) -> str:
        """Pause, resume, run now, edit or delete a monitor."""
        mid = quote(monitor_id, safe="")
        if action == "delete":
            await call.client.delete("agent", f"/monitors/{mid}")
            return f"Deleted monitor {monitor_id} (its past runs stay in your history)."
        if action == "run_now":
            m = await call.client.post("agent", f"/monitors/{mid}/run", {})
            return f"Running {render_monitor(m)}\nIt starts within ~5 minutes; read it with get_monitor_updates."
        body: dict[str, Any] = {}
        if action == "pause":
            body["enabled"] = False
        if action == "resume":
            body.update(enabled=True, fill_gap=fill_gap)
        if name is not None:
            body["name"] = name
        if schedule:
            body["schedule"] = schedule_body(schedule)
        if query is not None:
            body["query"] = query
        if companies:
            body["companies"] = to_company_in(companies)
        if not body:
            raise UserError("Nothing to change: give an action or fields to edit.")
        m = await call.client.patch("agent", f"/monitors/{mid}", body)
        return f"Updated {render_monitor(m)}"
