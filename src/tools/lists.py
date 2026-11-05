"""Company list tools: save_company_list, get_company_list, edit_company_list."""

from typing import Annotated, Any, Literal
from urllib.parse import quote

from fastmcp import FastMCP
from pydantic import BaseModel, Field

from src.config import Config
from src.formatting import clip, plural, to_json, when
from src.lenient import ItemList, JsonText, TokenList
from src.tools.common import Call, UserError, register
from src.tools.params import CompanyItem, drop_none, items, to_company_in


def render_list(d: dict[str, Any], max_companies: int = 60) -> str:
    """Render a company list with each company's identification status.

    Args:
        d (dict[str, Any]): List from the API.
        max_companies (int): Most companies to show.

    Returns:
        str: The text.
    """
    counts = ", ".join(f"{v} {k}" for k, v in (d.get("counts") or {}).items())
    lines = [
        f"Company list {d.get('list_id')} · \"{d.get('name')}\" · {plural(int(d.get('count') or 0), 'company', 'companies')} · "
        f"{d.get('status')}"
        + (f" ({counts})" if counts else "")
        + (f" · {d['added']} added" if d.get("added") is not None else "")
    ]
    if d.get("status") == "resolving":
        lines.append("Companies are still being identified; runs and monitors from this list wait for them, so you can use it now.")
    cs: list[dict[str, Any]] = d.get("companies") or []
    for c in cs[:max_companies]:
        p = c.get("profile") or {}
        desc = f" — {clip(p['description'], 90)}" if p.get("description") else ""
        lines.append(
            f"- {c.get('domain')}: {c.get('name') or p.get('name') or ''} [{c.get('identity_status')}"
            + (", corrected" if c.get("corrected") else "")
            + "]"
            + (f" ({c['error']})" if c.get("error") else "")
            + desc
        )
    if len(cs) > max_companies:
        lines.append(f"… {len(cs) - max_companies} more.")
    if d.get("skipped_count"):
        skipped = ", ".join(f'"{clip(s.get("value"), 40)}" ({s.get("reason")})' for s in (d.get("skipped") or [])[:5])
        lines.append(f"Skipped {d['skipped_count']}: {skipped}")
    bad = [c for c in cs if c.get("identity_status") in ("not_found", "failed")]
    if bad:
        lines.append(f"{plural(len(bad), 'company', 'companies')} could not be identified: fix them with edit_company_list(correct=…).")
    return "\n".join(lines)


class Correction(BaseModel):
    """Fix one company's identity."""

    domain: Annotated[str, Field(description="The domain as it is in the list now.")]
    new_domain: Annotated[str | None, Field(description="Its right domain.")] = None
    name: Annotated[str | None, Field(description="Its right name.")] = None
    other_names: Annotated[items(str, max_length=10) | None, ItemList, Field(description="Brands, former or local names.")] = None  # type: ignore[operator]


def register_list_tools(mcp: FastMCP, config: Config) -> None:
    """Register the lists toolset.

    Args:
        mcp (FastMCP): The server.
        config (Config): Server settings.
    """

    @register(
        mcp,
        config,
        name="save_company_list",
        title="Save a company list",
        description=(
            "Create a reusable list of companies (by website domain), or add companies to an existing list (give list_id). "
            "Use it for watchlists, portfolios, accounts or competitors that the user will research or monitor more than "
            "once: start_research(company_list_id) and create_monitor(company_list_id) use it, and a monitor follows later "
            "changes to the list. "
            "Give companies, or from_run_id to save the companies of a company research run. "
            "Each company is identified in the background (free)."
        ),
        toolset="lists",
        api="agent",
        annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True},
    )
    async def save_company_list(
        call: Call,
        companies: Annotated[
            items(CompanyItem, min_length=1, max_length=500) | None,  # type: ignore[operator]
            TokenList,
            Field(
                description='Companies by domain, e.g. ["stripe.com", {"domain":"wise.com","name":"Wise"}].',
            ),
        ] = None,
        from_run_id: Annotated[str | None, Field(description="Save the companies of this company research run as a new list.")] = None,
        name: Annotated[str | None, Field(description='List name (new lists only), e.g. "Portfolio" or "Competitors".')] = None,
        list_id: Annotated[str | None, Field(description="Add to this existing list instead of creating a new one.")] = None,
    ) -> str:
        """Create a list or add companies to one."""
        if (companies is not None) + (from_run_id is not None) != 1:
            raise UserError("Give exactly one of companies or from_run_id.")
        if from_run_id:
            data = await call.client.post("agent", f"/companies/lists/from-run/{quote(from_run_id, safe='')}", drop_none({"name": name}))
        elif list_id:
            data = await call.client.post(
                "agent", f"/companies/lists/{quote(list_id, safe='')}/companies", {"companies": to_company_in(companies or [])}
            )
        else:
            data = await call.client.post("agent", "/companies/lists", drop_none({"name": name, "companies": to_company_in(companies or [])}))
        return render_list(data or {}, 25)

    @register(
        mcp,
        config,
        name="get_company_list",
        title="Get company lists",
        description=(
            "Show one saved company list with each company's identification status (ready, resolving, not_found…), or with "
            "no list_id, all your lists. Free."
        ),
        toolset="lists",
        api="agent",
        annotations={"readOnlyHint": True, "idempotentHint": True},
    )
    async def get_company_list(
        call: Call,
        list_id: Annotated[str | None, Field(description="The list to show; leave out to list all lists.")] = None,
        format: Literal["text", "json"] = "text",
    ) -> str:
        """Show one list or all lists."""
        if not list_id:
            data = await call.client.get("agent", "/companies/lists")
            lists = data if isinstance(data, list) else (data or {}).get("lists") or []
            if format == "json":
                return to_json(lists)
            if not lists:
                return "No company lists yet. Create one with save_company_list."
            return "\n".join(
                f"- {lst.get('list_id')} · \"{lst.get('name')}\" · {plural(int(lst.get('count') or 0), 'company', 'companies')} · "
                f"{lst.get('status')} · updated {when(lst.get('updated_at'))}"
                for lst in lists
            )
        data = await call.client.get("agent", f"/companies/lists/{quote(list_id, safe='')}")
        return to_json(data) if format == "json" else render_list(data or {})

    @register(
        mcp,
        config,
        name="edit_company_list",
        title="Edit a company list",
        description=(
            "Change a saved company list: remove companies, correct one that was identified as the wrong business (new "
            "domain, name or other names), rename the list, or delete it. "
            "To add companies use save_company_list(list_id=…). Monitors that follow the list pick up the change on their next run."
        ),
        toolset="lists",
        api="agent",
        annotations={"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False},
    )
    async def edit_company_list(
        call: Call,
        list_id: Annotated[str, Field(description="The list to change.")],
        remove: Annotated[list[str] | None, TokenList, Field(description="Domains to remove.")] = None,
        correct: Annotated[Correction | None, JsonText, Field(description="Fix one company's identity.")] = None,
        rename: Annotated[str | None, Field(description="New list name.")] = None,
        delete: Annotated[bool, Field(description="Delete the whole list (monitors following it keep their last companies).")] = False,
    ) -> str:
        """Remove, correct, rename or delete."""
        lid = quote(list_id, safe="")
        if delete:
            await call.client.delete("agent", f"/companies/lists/{lid}")
            return f"Deleted company list {list_id}."
        done: list[str] = []
        for domain in remove or []:
            await call.client.delete("agent", f"/companies/lists/{lid}/companies/{quote(domain, safe='')}")
            done.append(f"removed {domain}")
        if correct:
            await call.client.patch(
                "agent",
                f"/companies/lists/{lid}/companies/{quote(correct.domain, safe='')}",
                drop_none({"domain": correct.new_domain, "name": correct.name, "other_names": correct.other_names}),
            )
            done.append(f"corrected {correct.domain}")
        if rename:
            await call.client.patch("agent", f"/companies/lists/{lid}", {"name": rename})
            done.append(f'renamed to "{rename}"')
        if not done:
            raise UserError("Nothing to change: give remove, correct, rename or delete.")
        data = await call.client.get("agent", f"/companies/lists/{lid}")
        return f"{'; '.join(done)}.\n{render_list(data or {}, 25)}"
