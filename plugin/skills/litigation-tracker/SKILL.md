---
name: litigation-tracker
description: "Use when the user wants lawsuits, legal disputes, class actions, settlements, verdicts, patent cases or court rulings involving companies, an industry or a person — for legal, risk, investor or competitive research. Builds a litigation table from the news with NewsCatcher and keeps it updated."
---

# Litigation tracker

Who sued whom, over what, where it stands, with sources.

Runs on the NewsCatcher MCP tools (`start_research`, `get_research`, `list_articles`, `create_monitor`). If missing,
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
1. Market or topic: `start_research(query="Lawsuits, class actions, settlements and court rulings involving <sector or companies> since <date>, with plaintiff, defendant, court or jurisdiction, claim, amount sought or awarded, status and date", mode="fast", max_rows=100)`.
2. Companies: `start_research(companies=[…], query="lawsuits, class actions, settlements, verdicts, regulatory litigation", lookback_days=180)`.
3. Every mention of one case: `list_articles(query="\"<Company>\" AND (lawsuit OR sued OR \"class action\" OR settlement OR verdict) AND \"<case keyword>\"", from="12 months ago")`.
4. `get_research(run_id, wait_seconds=300)`; `create_monitor(from_run_id=run_id)` for new filings and rulings.

## Deliver
Table: date · parties · court/jurisdiction · claim · amount · status (filed / motion / ruling / settled / dismissed /
appeal) · source; then the biggest exposures and the next expected steps.

## Quality bar
- Show at most 25 rows inline (most important or newest first) and say how many there are; `export_research` gives the full table as a file.
- Status as of the latest article; filed claims are allegations.
- One row per case; multiple suits on the same issue are separate rows unless consolidated.
- Not legal advice.

## Done when
Cases in scope are listed with parties, status and sources.
