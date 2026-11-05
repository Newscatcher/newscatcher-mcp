"""Builds the FastMCP server: instructions, tools, guides, and the middleware for toolsets and input errors."""

from collections.abc import Sequence
from typing import Any

import pydantic
from fastmcp import FastMCP
from fastmcp.exceptions import ValidationError as FastMCPValidationError
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from fastmcp.tools import Tool, ToolResult
from starlette.requests import Request
from starlette.responses import JSONResponse

from src import VERSION
from src.analytics import AnalyticsFlushMiddleware, init_analytics
from src.auth import RequireApiKeyMiddleware, request_toolsets
from src.config import Config
from src.guides import register_guides
from src.tools.common import text_result
from src.tools.lists import register_list_tools
from src.tools.monitors import register_monitor_tools
from src.tools.news import register_news_tools
from src.tools.research import register_research_tools

INSTRUCTIONS = """NewsCatcher: news search across every language plus a research agent that builds verified datasets from the news.

Pick the tool by the question:
- What happened / latest news / coverage of a company, person or topic (last 30 days): search_news. Start with effort=medium; low is faster and cheaper, high is best for hard questions (~25 s).
- How many articles, every article, exact keyword or boolean matching, or news older than 30 days (up to 12 months): list_articles (count_only=true for just the number).
- Trends, spikes, share of voice over time: count_articles.
- How big one story is, who covered it first: get_story with a story id from search_news.
- A table of events with sources (deals, layoffs, funding rounds, recalls, lawsuits…): start_research with a query, then get_research to wait for it. Fast takes minutes; standard/max are deeper and slower.
- Recent news about specific companies (a watchlist, portfolio, accounts, competitors): start_research with companies or a company_list_id.
- Keep any of these updated on a schedule: start_research(keep_updated=true) or create_monitor; read results with get_monitor_updates.
- Reusable sets of companies: save_company_list, get_company_list, edit_company_list.
- Credits, limits, plan: get_account.

Dates: "this week" = Monday to now, "last week" = the previous Monday–Sunday, "last month" = the previous calendar month (UTC); a window without an end ends today. Say the exact dates you used.

Results give headlines, one-line summaries, sources, dates and links; cite the links. To read an article itself, open its URL with a web fetch tool. Research runs and monitors cost credits and take minutes: confirm big jobs (standard/max, many companies, hourly schedules) with the user first; start_research(dry_run=true) shows the time and list-price cost for free. Ids (story, run, list, monitor) come from earlier results; never invent them.

This hosted server has no file tools: export_research, save_as and csv_path (which some skills mention) are not available. Give tables in the answer, page longer ones with get_research(rows_offset=…, rows_limit up to 200), and say the full file can be downloaded from the run in the NewsCatcher platform."""


def _toolset(tool: Tool) -> str | None:
    """The toolset a tool belongs to (its tag).

    Args:
        tool (Tool): A registered tool.

    Returns:
        str | None: Toolset name.
    """
    return next(iter(tool.tags), None) if tool.tags else None


def _invalid_arguments(err: pydantic.ValidationError) -> str:
    """Short, actionable text for bad arguments: ``Invalid arguments: query: <fix>; limit: <fix>``.

    Args:
        err (pydantic.ValidationError): The validation error.

    Returns:
        str: The text.
    """
    parts: list[str] = []
    for e in err.errors():
        loc = ".".join(str(x) for x in e.get("loc", ())) or "arguments"
        msg = str(e.get("msg", "invalid"))
        parts.append(f"{loc}: {msg.removeprefix('Value error, ')}")
    return "Invalid arguments: " + "; ".join(parts)


class ToolsetMiddleware(Middleware):
    """Shows only the toolsets this connection asked for (``?tools=``) and returns readable input errors."""

    def __init__(self, config: Config) -> None:
        """Create the middleware.

        Args:
            config (Config): Server settings.
        """
        self.config = config

    async def on_list_tools(
        self, context: MiddlewareContext[Any], call_next: CallNext[Any, Sequence[Tool]]
    ) -> Sequence[Tool]:
        """Filter the tool list by the connection's toolsets.

        Args:
            context (MiddlewareContext[Any]): Request context.
            call_next (CallNext[Any, Sequence[Tool]]): Next handler.

        Returns:
            Sequence[Tool]: The visible tools.
        """
        tools = await call_next(context)
        allowed = request_toolsets(self.config)
        return [t for t in tools if _toolset(t) in allowed]

    async def on_call_tool(self, context: MiddlewareContext[Any], call_next: CallNext[Any, ToolResult]) -> ToolResult:
        """Refuse tools outside the connection's toolsets and turn validation errors into isError results.

        Args:
            context (MiddlewareContext[Any]): Request context.
            call_next (CallNext[Any, ToolResult]): Next handler.

        Returns:
            ToolResult: The result.
        """
        allowed = request_toolsets(self.config)
        name = getattr(context.message, "name", "")
        if context.fastmcp_context is not None:
            tool = await context.fastmcp_context.fastmcp.get_tool(name)
            if tool is not None and _toolset(tool) not in allowed:
                return text_result(
                    f"Error: {name} is not enabled on this connection (toolsets: {', '.join(sorted(allowed))}).", is_error=True
                )
        try:
            return await call_next(context)
        except FastMCPValidationError as err:
            if isinstance(err.__cause__, pydantic.ValidationError):
                return text_result(_invalid_arguments(err.__cause__), is_error=True)
            raise


def build_server(config: Config) -> FastMCP:
    """Create the MCP server with every tool registered.

    Every toolset is registered; ``ToolsetMiddleware`` hides the ones a connection did not ask for, so one deployment
    can serve ``/mcp`` and ``/mcp?tools=news`` alike.

    Args:
        config (Config): Server settings.

    Returns:
        FastMCP: The server.
    """
    mcp = FastMCP(
        "newscatcher",
        instructions=INSTRUCTIONS,
        version=VERSION,
        website_url="https://www.newscatcherapi.com",
        middleware=[ToolsetMiddleware(config)],
    )
    register_news_tools(mcp, config)
    register_research_tools(mcp, config)
    register_list_tools(mcp, config)
    register_monitor_tools(mcp, config)
    register_guides(mcp)

    @mcp.custom_route("/health", methods=["GET"])
    async def health(request: Request) -> JSONResponse:
        """Liveness check for uptime monitors; never calls the NewsCatcher APIs.

        Args:
            request (Request): The HTTP request.

        Returns:
            JSONResponse: ``{"ok": true, "version": ...}``.
        """
        return JSONResponse({"ok": True, "version": VERSION})

    return mcp


def create_app(config: Config) -> tuple[FastMCP, Any]:
    """Build the server and its ASGI app: stateless Streamable HTTP at ``/mcp``, a key required on every POST.

    Args:
        config (Config): Server settings.

    Returns:
        tuple[FastMCP, Any]: The server and the ASGI app.
    """
    mcp = build_server(config)
    # Must run before the ASGI app is built: it wraps FastMCP's app factories (see analytics.py).
    posthog = init_analytics(mcp, config)
    # stateless_http is mandatory on serverless: a request can land on a cold instance with no memory of a session.
    app = mcp.http_app(path="/mcp", stateless_http=True)
    app.add_middleware(RequireApiKeyMiddleware, config=config, mcp_path="/mcp")
    if posthog is not None:
        app.add_middleware(AnalyticsFlushMiddleware, client=posthog)
    return mcp, app
