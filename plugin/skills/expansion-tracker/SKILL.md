---
name: expansion-tracker
description: "Use when the user wants growth and footprint signals: new offices, plants, factories, data centers, market entries, store openings or closures, relocations, hiring sprees or big investment pledges; for sales triggers, real estate, economic development, supply chain or competitive intelligence. Tracks expansion news with NewsCatcher."
---

# Expansion tracker

Where companies are opening, building, entering or leaving, with a source per move.

Runs on the NewsCatcher MCP tools (see the `newscatcher` skill for setup, costs and errors).

## Ask first (only what you can't infer)
- Companies or a sector/geography, which moves (openings, closures, both), and the window. Default: 30 days.

## Before you run
- Window or size missing? Ask once: one multiple-choice question, recommended option first (e.g. "Last 30 days
  (Recommended)", "Fast, 50 rows (Recommended)"). Skip it when the user gave both or said "just run it".
- Standard/max, more than 20 companies or keep_updated: repeat the call with `dry_run=true` first (free) and show
  its time and cost in that question.
- Set up a monitor only when the user wants this regularly ("every week", "keep me posted"); not on one-off asks.
- While it runs, keep calling `get_research(run_id, wait_seconds=300)`; if you must stop first, say it is still
  running and ask the user to say "refresh".

## Run
- **Geography or sector:** `start_research(query="New offices, factories, plants, data centers, store openings and market entries announced since <date> in <region> by <sector> companies: company, location, type, investment, jobs, date", mode="fast", max_rows=100)`,
  then `get_research(run_id=…, wait_seconds=300)`.
- **Companies:** `start_research(companies=[…], query="new offices, plants, market entry, expansion, store openings and closures, hiring", lookback_days=60)`.
- **Spot check:** `search_news(query="<Company> opens OR expands OR new plant OR new office", window="30d", group="story")`.
- Local press finds the small moves: add `countries=[…]` and local-language words (e.g. "nueva planta", "neues Werk").

## Deliver
| Date | Company | Location | Move | Investment / jobs (as reported) | Source |
Then the biggest commitments and any closures or retreats.

## Quality bar
- Show at most 25 rows inline (most important or newest first) and say how many there are; `export_research` gives the full table as a file.
- Announced versus completed: label which.
- Investment and job numbers as reported; "up to" stays.
- One row per site.

## Keep it running
`create_monitor(company_list_id=…, query="expansion, new office, new plant, closures", schedule={"every":"week"})`.

## Done when
The scope is covered with one sourced row per move, announced and completed moves labelled.
