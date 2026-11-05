---
name: government-contracts
description: "Use when the user wants public contract awards, tenders and procurement wins reported in the news: defense, IT, infrastructure, healthcare or consulting contracts, who won, from which agency, for how much. Builds a contract-awards table with the NewsCatcher research agent; for sales, competitive intelligence and investors."
---

# Government contracts

Who won which public contracts, from whom, for how much, with a source per row.

Runs on the NewsCatcher MCP tools (see the `newscatcher` skill for setup, costs and errors).

## Ask first (only what you can't infer)
- Sector (defense, IT, construction…), buyer (country, agency) or the companies to watch, and the window. Default: 30 days.

## Before you run
- Window or size missing? Ask once: one multiple-choice question, recommended option first (e.g. "Last 30 days
  (Recommended)", "Fast, 50 rows (Recommended)"). Skip it when the user gave both or said "just run it".
- Standard/max, more than 20 companies or keep_updated: repeat the call with `dry_run=true` first (free) and show
  its time and cost in that question.
- Set up a monitor only when the user wants this regularly ("every week", "keep me posted"); not on one-off asks.
- While it runs, keep calling `get_research(run_id, wait_seconds=300)`; if you must stop first, say it is still
  running and ask the user to say "refresh".

## Run
1. Sector scan: `start_research(query="Government contracts awarded since <date> in <country> for <sector>: contractor, agency or buyer, contract value, duration, scope, award date", mode="fast", max_rows=100)`,
   then `get_research(run_id=…, wait_seconds=300)`.
2. Companies: `start_research(companies=[…], query="government contract awards, tenders won, framework agreements, procurement", lookback_days=30)`.
3. One award in detail: `search_news(query="<Contractor> <agency> contract awarded", window="30d", group="story")`, then
   `get_story` for the original announcement.
4. Non-English buyers: search in the local language too (e.g. "adjudica contrato", "Auftrag erhalten").

## Deliver
| Date | Contractor | Buyer / agency | Value (as reported) | Scope | Duration | Source |
Then the largest awards, repeat winners and buyers that stand out.

## Quality bar
- Show at most 25 rows inline (most important or newest first) and say how many there are; `export_research` gives the full table as a file.
- Values as reported with currency; "up to" and ceiling values stay labelled as such.
- Awards, protests and cancellations are separate rows.
- News covers announced awards; official procurement portals are the record. Say so.

## Keep it running
`create_monitor(from_run_id=…, schedule={"every":"week","weekday":0,"at":"08:00"})`.

## Done when
The scope and window are covered with sourced rows, values labelled as reported.
