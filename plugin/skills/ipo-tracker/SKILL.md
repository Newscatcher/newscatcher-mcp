---
name: ipo-tracker
description: "Use when the user wants IPOs and listings: filings, roadshows, pricings, first-day trading, delayed or withdrawn offerings, SPAC deals and direct listings, by exchange, country or sector. Builds an IPO table from the news with the NewsCatcher research agent and can keep it updated."
---

# IPO tracker

Who is going public, where, at what size and price, with a source per row.

Runs on the NewsCatcher MCP tools (see the `newscatcher` skill for setup, costs and errors).

## Ask first (only what you can't infer)
- Scope: exchange or country (e.g. Nasdaq/NYSE, Hong Kong, India), sector, and stage (filed, priced, debuted,
  withdrawn). Default: all stages, last 30 days.

## Before you run
- Window or size missing? Ask once: one multiple-choice question, recommended option first (e.g. "Last 30 days
  (Recommended)", "Fast, 50 rows (Recommended)"). Skip it when the user gave both or said "just run it".
- Standard/max, more than 20 companies or keep_updated: repeat the call with `dry_run=true` first (free) and show
  its time and cost in that question.
- Set up a monitor only when the user wants this regularly ("every week", "keep me posted"); not on one-off asks.
- While it runs, keep calling `get_research(run_id, wait_seconds=300)`; if you must stop first, say it is still
  running and ask the user to say "refresh".

## Run
1. `start_research(query="IPOs on <exchange/country> announced, filed, priced or withdrawn since <date>: company, exchange, ticker, stage, offer size, price range or final price, first-day move, lead underwriters, date", mode="fast", max_rows=100)`.
2. `get_research(run_id=…, wait_seconds=300)`; `export_research(run_id=…, file_format="xlsx")` for the sheet.
3. Quick check on one name: `search_news(query="<Company> IPO pricing", window="14d", group="story")`.
4. Pipeline heat (optional): `count_articles(queries=["IPO AND (filing OR files OR prices OR debut)"], from="<90 days ago>", interval="week")`.

## Deliver
| Date | Company | Exchange · ticker | Stage | Size | Price | First day | Underwriters | Source |
Then: the biggest deals, withdrawals or delays and their stated reasons, and the trend if you counted.

## Quality bar
- Show at most 25 rows inline (most important or newest first) and say how many there are; `export_research` gives the full table as a file.
- One row per company per stage change (filing and pricing are two rows if both happened in the window).
- Sizes and prices as reported, with currency; "expected" stays "expected".
- No views on whether to buy.

## Keep it running
`start_research(…, keep_updated=true)` or `create_monitor(from_run_id=…, schedule={"every":"day","at":"08:00"})`.

## Done when
The table covers the scope and window with a source per row, and stages are current as of the run.
