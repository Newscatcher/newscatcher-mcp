---
name: executive-moves-tracker
description: "Use when the user wants leadership changes — new CEOs, CFOs, CTOs, board appointments, departures, resignations, firings — at companies in a sector, region or account list; for sales triggers, recruiting, investor monitoring or competitive intelligence. Builds a table of executive moves from the news with the NewsCatcher research agent."
---

# Executive moves tracker

Who joined, left or changed roles at the top, with the date and source.

Runs on the NewsCatcher MCP tools (`start_research`, `get_research`, `create_monitor`). If missing, see the
`newscatcher` skill.

## Before you run
- Window or size missing? Ask once: one multiple-choice question, recommended option first (e.g. "Last 30 days
  (Recommended)", "Fast, 50 rows (Recommended)"). Skip it when the user gave both or said "just run it".
- Standard/max, more than 20 companies or keep_updated: repeat the call with `dry_run=true` first (free) and show
  its time and cost in that question.
- Set up a monitor only when the user wants this regularly ("every week", "keep me posted"); not on one-off asks.
- While it runs, keep calling `get_research(run_id, wait_seconds=300)`; if you must stop first, say it is still
  running and ask the user to say "refresh".

## Run
1. Market-wide: `start_research(query="New CEO, CFO, CTO and other C-level appointments and departures at <sector> companies in <geography> since <date>, with company, person, new role, previous role or employer, effective date and source", mode="fast", max_rows=100)`.
2. Account list: `start_research(company_list_id=…, query="executive appointments, departures, board changes", lookback_days=60)`,
   then `create_monitor(company_list_id=…, query=<same>)` to catch new moves.
3. `get_research(run_id, wait_seconds=300)`.

## Deliver
Table: date · company · person · change (appointed / departed / promoted) · role · from (previous role/company) ·
source. For sales: one line on why the move matters (new leaders review vendors in their first 90 days).

## Quality bar
- Show at most 25 rows inline (most important or newest first) and say how many there are; `export_research` gives the full table as a file.
- Effective date if reported, else announcement date — say which.
- Interim roles marked interim; rumours excluded.

## Done when
Each move has a person, company, role, date and source.
