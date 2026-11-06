---
name: company-brief
description: "Use when the user wants to know what is going on at one company — recent news, key events (funding, M&A, leadership, product, legal, layoffs, earnings), risks and momentum, before a meeting, call, investment memo or outreach. Produces a dated, sourced company news brief from the NewsCatcher research agent and news search."
---

# Company brief

What happened at one company recently, ranked by importance, with dates and sources.

Runs on the NewsCatcher MCP tools (`start_research`, `get_research`, `search_news`, `count_articles`). If missing, see
the `newscatcher` skill.

## Ask first (only what's missing)
- The company's website domain (it pins the right company: `stripe.com`, not "Stripe"). If only a name is given,
  find the domain with a quick `search_news` or web search and confirm when ambiguous.
- Window: default 30 days (`lookback_days` up to 365).
- Purpose (sales call, investment, partnership, risk) — it decides what to lead with.

## Before you run
- Window or size missing? Ask once: one multiple-choice question, recommended option first (e.g. "Last 30 days
  (Recommended)", "Fast, 50 rows (Recommended)"). Skip it when the user gave both or said "just run it".
- Standard/max, more than 20 companies or keep_updated: repeat the call with `dry_run=true` first (free) and show
  its time and cost in that question.
- Set up a monitor only when the user wants this regularly ("every week", "keep me posted"); not on one-off asks.
- While it runs, keep calling `get_research(run_id, wait_seconds=300)`; if you must stop first, say it is still
  running and ask the user to say "refresh".

## Run
1. `start_research(companies=["<domain>"], lookback_days=<days>, wait_seconds=240)`. The company agent identifies
   the company, reads its news, newsroom and the web, and returns one row per story with story_type, importance,
   outlets and a link. If it is still running, `get_research(run_id, wait_seconds=240)`.
2. For anything in the last 48 hours the run may miss, `search_news(query="<Company name>", window="2d", group="story")`.
3. Optional momentum: `count_articles(queries=["\"<Company name>\""], from=<90 days ago>, interval="week")`.

## Deliver
```
**<Company> (<domain>) — news, <window>**
**In one line:** the most important development.
**Key events** (newest first): date · type · what happened · [source](url) · N outlets
**Signals:** funding/financials · people · product · partnerships · legal/regulatory · risks
**Coverage:** found / thin / none (from the run's coverage line)
```
Tailor the lead to the purpose: for sales, recent triggers and priorities; for risk, legal and negative stories.

## Quality bar
- Show at most 25 rows inline (most important or newest first) and say how many there are; `export_research` gives the full table as a file.
- Importance and outlet counts come from the run; don't upgrade a one-outlet story into a trend.
- If coverage is `no_news` or `thin`, say so; don't pad with generic company facts.
- Company facts not in the news (founding year, HQ, investors) are out of scope; use web search and say where they
  came from.

## Done when
The user can walk into the meeting knowing the last month's events at this company, each with a link.
