"""Reference guides as MCP resources, and workflow prompts (slash commands in Claude Code).

Short on purpose: tool descriptions carry the routing, guides carry syntax and recipes.
"""

from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

GUIDES: dict[str, dict[str, str]] = {
    "query-syntax": {
        "title": "Query syntax for search_news, list_articles and count_articles",
        "text": """# Query syntax

## search_news (relevance)
- Plain language or keywords, any language: "Nvidia guidance for next quarter", "Siemens Energy Auftragseingang".
- Upper-case NOT drops a term: `Apple NOT iPhone`, `Tesla NOT "Model Y"`.
- Narrow with languages, countries, sources (domains), min_newsrooms (story size), window (`2h`, `1d`, `7d`, `30d`).
- group: `diverse` (default), `story` (one article per story: distinct events), `all`.

## list_articles / count_articles (boolean, exact)
- Operators: `AND`, `OR`, `NOT`, parentheses, `"exact phrase"`, `+must`, `-mustnot`, `wild*`, `NEAR("a", "b", 5)`.
- Bare words are all required: `Tesla recall` = Tesla AND recall. Use OR for synonyms: `(layoff OR layoffs OR "job cuts")`.
- Quote company names with spaces: `"Goldman Sachs"`. Add an AND clause to avoid namesakes: `"Apple" AND (iPhone OR Cupertino OR "Tim Cook")`.
- search_in: `title` for headline mentions only (more precise), `title_body` (default), `*_translated` to match the English translation of other languages.
- from / to: ISO dates or phrases (`30 days ago`). Up to 12 months back. When paging, keep `to` fixed to the first page's window end.
- A query reaches its first 1,000 articles (page × page_size ≤ 1,000); total counts are exact beyond that.

## Picking
| Question | Tool |
|---|---|
| Best answers, latest developments | search_news |
| How many / every article / older than 30 days | list_articles |
| Volume over time, share of voice | count_articles |
| One event's full coverage | get_story |
| A verified table of events or company news | start_research |""",
    },
    "research-agent": {
        "title": "Research agent: modes, kinds, costs and monitors",
        "text": """# Research agent

start_research runs NewsCatcher's research agent in the background; get_research waits for it and returns the table.

## Two kinds
- **Events**: `query` describes the dataset, with its time window: "Series A rounds by European fintech startups since September 1, 2026". The agent picks the columns (always with source_url). One row per event.
- **Companies**: `companies` (domains) or `company_list_id`, optional `query` to keep only some stories ("funding, M&A, leadership changes"), `lookback_days` (default 30). One row per story with the company first; `get_research` also shows each company's coverage (found / no_news / not_searched).

## Modes (events)
- fast (default): one agent, 3–10 minutes, cheapest.
- standard: deep research: planned slices, each row checked against its sources, a cited briefing. 10–30 minutes.
- max: strongest models, highest recall, highest cost.
Company runs have one quality.

## Writing a good events query
- Say what counts as a row: "acquisitions of US community banks" beats "bank news".
- Give the window: "since October 1, 2026", "in Q3 2026", "last 30 days".
- Name the fields you need if they matter: "with deal value and acquirer".
- Describe the events, not the coverage: "layoffs at US tech companies in October 2026", not "news articles about tech layoffs".
- Not a fit: how-to advice, static company facts (founding year, HQ, investors), single-fact lookups (use search_news).
- `dry_run=true` checks the query (window, wording) and shows the time, list-price cost and your balance, free.

## Before and while it runs
- Missing window or size: ask the user once, one multiple-choice question with the recommended option first; skip it when they gave both or said "just run it" (then fast, 50 rows, last 30 days).
- Keep calling get_research(run_id, wait_seconds=300) until it finishes. If you have to stop first, say it is still running and ask the user to say "refresh"; refresh means get_research on the same run id, never a new run.

## Keeping it updated
- Set up a monitor when the user wants results regularly ("every week", "keep me posted"); don't push one on a one-off request.
- `keep_updated=true` on start_research makes a monitor when the run succeeds.
- create_monitor(from_run_id) does the same for a finished run; create_monitor(companies | company_list_id, query) watches companies.
- get_monitor_updates shows what each run delivered (new or update). Empty runs are free.

## Costs
Research runs and monitors are billed in credits from the same balance as searches when they finish; failed and cancelled runs are free. See your plan's prices in the NewsCatcher docs (newscatcherapi.com/docs).""",
    },
}


def register_guides(mcp: FastMCP) -> None:
    """Register the guide resources and the workflow prompts.

    Args:
        mcp (FastMCP): The server.
    """
    for slug, guide in GUIDES.items():
        _register_guide(mcp, slug, guide["title"], guide["text"])

    @mcp.prompt(name="news_briefing", title="News briefing", description="A cited briefing on a topic, company or person from the last days of news.")
    def news_briefing(
        topic: Annotated[str, Field(description="What the briefing is about")],
        window: Annotated[str | None, Field(description="e.g. 1d, 7d (default 7d)")] = None,
    ) -> str:
        """Build the news briefing prompt.

        Args:
            topic (str): Subject of the briefing.
            window (str | None): How far back.

        Returns:
            str: The prompt text.
        """
        return (
            f'Write a news briefing on "{topic}" covering the last {window or "7d"}. Use the newscatcher tools: search_news '
            "(effort=medium, group=story, limit 20) for the main stories, get_story for the biggest ones, and count_articles "
            "if volume matters. Group by theme, lead with what changed, cite every claim with its link, and end with what to watch next."
        )

    @mcp.prompt(name="company_watch", title="Company watch", description="Recent news about a set of companies, optionally kept updated.")
    def company_watch(
        companies: Annotated[str, Field(description="Company domains, comma-separated")],
        focus: Annotated[str | None, Field(description="e.g. funding, M&A, leadership")] = None,
    ) -> str:
        """Build the company watch prompt.

        Args:
            companies (str): Company domains.
            focus (str | None): Kinds of news to focus on.

        Returns:
            str: The prompt text.
        """
        return (
            f"Get recent news for these companies: {companies}" + (f", focusing on {focus}" if focus else "")
            + ". Use start_research with the companies" + (f' and query "{focus}"' if focus else "")
            + ", wait with get_research, then summarise per company: the most important stories first, with dates and links, "
            "and note companies with no news. If I want to keep watching them, set up a monitor."
        )

    @mcp.prompt(name="event_dataset", title="Event dataset", description="Build a table of events (deals, layoffs, recalls, funding rounds…) from the news.")
    def event_dataset(request: Annotated[str, Field(description="The events, with a time window")]) -> str:
        """Build the event dataset prompt.

        Args:
            request (str): The events to collect, with a window.

        Returns:
            str: The prompt text.
        """
        return (
            f'Build a dataset: "{request}". Use start_research (mode fast unless I ask for depth), wait for it with '
            "get_research, show the table and flag rows that look off."
        )


def _register_guide(mcp: FastMCP, slug: str, title: str, text: str) -> None:
    """Register one guide as a static Markdown resource.

    Args:
        mcp (FastMCP): The server.
        slug (str): Guide slug.
        title (str): Guide title.
        text (str): Markdown body.
    """

    @mcp.resource(f"newscatcher://guides/{slug}", name=slug, title=title, description=title, mime_type="text/markdown")
    def guide() -> str:
        """Return the guide text.

        Returns:
            str: Markdown.
        """
        return text
