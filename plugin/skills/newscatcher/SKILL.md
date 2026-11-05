---
name: newscatcher
description: "Use for anything about the news or current events, and for setting up or troubleshooting NewsCatcher — what happened, latest developments, coverage of a company, person, topic or event, how many articles mention something, news trends, a table of events (deals, layoffs, funding, recalls), watching companies or topics on a schedule. Maps each kind of question to the right NewsCatcher tool, explains costs, and fixes setup and error problems."
---

# NewsCatcher

NewsCatcher covers the news in every language and runs a research agent on top of it. This skill is the map: which
tool answers which question, what it costs, and how to fix problems. Use-case skills (briefings, company research,
adverse media, trackers…) build on it.

Runs on the NewsCatcher MCP tools. If tools named `search_news`, `start_research` etc. are not available, NewsCatcher
is not set up: see **Setup** below. Install only if the human asked you to; otherwise tell them how and stop.

## Pick the tool

```
Latest news / what happened / coverage of X (last 30 days)  → search_news
How many articles / every article / exact keywords           → list_articles (count_only=true for just the number)
Every matching article into a file (CSV/JSON, up to 1,000)   → list_articles(save_as="csv")
Who covers a topic: top outlets, authors, countries          → list_articles(tally=["source","country","language"]) (one pass)
News older than 30 days (up to 12 months)                    → list_articles with from/to
Volume over time, spikes, share of voice                     → count_articles
How big is one story, who reported it first                  → get_story (story id from search_news)
A table of events with sources (deals, layoffs, recalls…)    → start_research(query) → get_research
Recent news about specific companies                         → start_research(companies) → get_research
Keep a research table or company watch updated               → start_research(keep_updated) or create_monitor
Reusable company sets (portfolio, accounts, competitors)     → save_company_list / get_company_list / edit_company_list
Credits, limits, plan                                         → get_account
```

Not a fit: general web pages, documentation, how-to advice, static company facts (founding year, HQ, investors):
use web search. To read an article itself, open its URL with a web fetch tool; NewsCatcher gives headlines,
one-line summaries, sources, dates and links.

## Costs (credits, from one balance)

| Call | Cost |
|---|---|
| search_news | 1 (low) / 5 (medium, default) / 10 (high) |
| list_articles | 5 per page (save_as: 5 per 100 articles) |
| count_articles | 5 per bucket per query (max 60 calls) |
| get_story | 1 |
| get_account, get_research, get_company_list, get_monitor, get_monitor_updates | free |
| start_research, monitors | billed per run (fast < standard < max; company runs per company); failed and empty runs are free |

Confirm with the user before standard/max runs, runs over 20 companies, hourly monitors or more than 30 count calls.

## Before a paid run (start_research, create_monitor)

- **Ask once, only for what's missing.** If the time window or the size is missing, ask a single multiple-choice
  question (the host's question picker when it has one), recommended option first, e.g. window: "Last 30 days
  (Recommended)", "Last 7 days", "Since a date"; size: "Fast, 50 rows (Recommended)", "Standard, verified with a
  briefing", "Max". Put both in the same question round; never ask twice in one run.
- **Skip the question** when the user gave both, or said "just run it": then fast, 50 rows, last 30 days.
- **Big jobs** (standard/max, more than 20 companies, keep_updated): call start_research with the same arguments
  plus `dry_run=true` first (free) and show its time and cost in that one question.
- **Monitors only on request.** Offer keep_updated or create_monitor when the user asks for something regularly
  ("every week", "keep me posted", "alert me", "track"). Don't push one on a one-off request.
- **Describe events, not coverage.** "Layoffs at US tech companies in October 2026, with company, jobs cut and
  date", not "news articles about tech layoffs". Event + who/where + window + the fields you need.

## While a run is going

- Say one line when it starts ("Running, usually 3–10 minutes; I'll post the table when it's done.") and nothing
  more until the results, unless the user asks.
- Keep calling `get_research(run_id, wait_seconds=300)` until it finishes; it waits on the server, so no sleep
  timers are needed. Don't build the table from other searches meanwhile.
- In a chat app that does not bring you back later, do not end your turn to wait: keep calling get_research in this
  turn. If you are running low on steps, stop cleanly: say it is still running, give the run id, and ask the user
  to say "refresh".
- The run keeps going if you stop; "refresh" later means `get_research` on the same run id, never a new run.

## Habits that give better answers

- search_news: start with effort=medium; use group=story when you want distinct events, min_newsrooms to keep only
  stories several newsrooms covered, window (`2h`, `1d`, `7d`, `30d`) for recency.
- list_articles is exact boolean matching: quote names (`"Goldman Sachs"`), OR synonyms (`(layoff OR layoffs OR
  "job cuts")`), search_in=["title"] for precision. When paging keep `to` fixed to the first page's window end.
- Cite every claim with the article link; say when coverage is thin (1 newsroom) or one-sided.
- Research runs take minutes: start_research, then get_research(run_id, wait_seconds=120–300). Show at most 25
  rows; its "Counts over all N rows" line gives totals (types, actors, investors, amounts) without paging.
  export_research writes the full table to a file; `exclude_rows` leaves out duplicates you found.
- Reports: search_news, list_articles and count_articles take `save_as` (local setups), and the pr-coverage-report,
  share-of-voice, competitor-intelligence and weekly-digest skills turn those files into an HTML report with
  `scripts/render-report.mjs`, so numbers and clips are never retyped.

## Setup

- **Claude Code (plugin):** `/plugin marketplace add <repo>` then `/plugin install newscatcher@newscatcher`; it asks
  for the API key once and keeps it in secure storage.
- **Claude Code (MCP only):** `claude mcp add --transport stdio --env NEWSCATCHER_API_KEY=$NEWSCATCHER_API_KEY newscatcher -- npx -y newscatcher-mcp`
- **Cursor / Claude Desktop / Codex:** an MCP server entry running `npx -y newscatcher-mcp` with env
  `NEWSCATCHER_API_KEY`.
- API keys: https://platform.newscatcherapi.com. Never paste a key into a file the user commits.

Check it works: call `get_account` (free). A plan name and balance means the key works.

## When something fails

| Error | Do |
|---|---|
| 401 | Key missing or wrong: set NEWSCATCHER_API_KEY / reconfigure the plugin |
| 402 | Balance too low: tell the user to top up; nothing was charged |
| 403 | Plan limit (limit/page_size too big, Enterprise field, mode or rows): lower it |
| 422 | Fix the parameter the message names; don't retry unchanged |
| 429 | Wait the seconds given, retry once |
| 503 on list_articles with an old window | The archive part can be down; keep to the last 30 days and say so |
| n/a buckets in count_articles | Those buckets could not be counted (archive outage or timeout); report the others and name the gap |
| Run still going | get_research again with a longer wait_seconds |

Never invent results, ids or links when a call fails: report the failure and what you tried.
