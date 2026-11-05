---
name: ma-deal-tracker
description: "Use when the user wants mergers and acquisitions — announced, pending or closed deals, acquirer, target, deal value, sector, status — for an industry, region or company, over a period; for M&A research, corporate development, banking, competitive or market analysis. Builds an M&A deal table from the news with the NewsCatcher research agent."
---

# M&A deal tracker

Announced and completed deals with acquirer, target, value, status and source.

Runs on the NewsCatcher MCP tools (`start_research`, `get_research`, `export_research`, `create_monitor`). If missing,
see the `newscatcher` skill.

## Before you run
- Window or size missing? Ask once: one multiple-choice question, recommended option first (e.g. "Last 30 days
  (Recommended)", "Fast, 50 rows (Recommended)"). Skip it when the user gave both or said "just run it".
- Standard/max, more than 20 companies or keep_updated: repeat the call with `dry_run=true` first (free) and show
  its time and cost in that question.
- Set up a monitor only when the user wants this regularly ("every week", "keep me posted"); not on one-off asks.
- While it runs, keep calling `get_research(run_id, wait_seconds=300)`; if you must stop first, say it is still
  running and ask the user to say "refresh".

## Run
1. `start_research(query="Mergers and acquisitions announced in <sector> in <geography> since <date>, with acquirer, target, deal value, deal type (acquisition, merger, stake), status and announcement date", mode="fast", max_rows=100)`.
   Use mode="standard" when deal values and status must be verified, or for a board-ready list.
2. `get_research(run_id, wait_seconds=300)`; `export_research` for the file.
3. For one company's deal history: `start_research(companies=["<domain>"], query="acquisitions, mergers, divestitures, stake purchases", lookback_days=365)`.
4. `create_monitor(from_run_id=run_id)` for new deals.

## Deliver
Table: announced date · acquirer · target · value (as reported) · type · status (announced / pending approval /
closed / terminated) · source. Then: deal count and disclosed value, the largest deals, active acquirers.

## Quality bar
- Show at most 25 rows inline (most important or newest first) and say how many there are; `export_research` gives the full table as a file.
- One row per deal; rumours ("in talks", "exploring a sale") only when asked, labelled as such.
- Status as of the latest coverage; closed deals keep their announcement date and add the close date if reported.

## Done when
Every deal in scope has a row with a source, and rumours are separated from announced deals.
