---
name: bankruptcy-distress
description: "Use when the user wants bankruptcies, insolvencies, restructurings, missed debt payments, covenant breaches, going-concern warnings, rating downgrades or distressed sales, for credit risk, collections, suppliers, lenders or investors; across a sector or for a list of companies. Builds a distress table or company watch from the news with NewsCatcher."
---

# Bankruptcy and distress watch

Which companies show financial distress, what kind, and since when, with sources.

Runs on the NewsCatcher MCP tools (see the `newscatcher` skill for setup, costs and errors).

## Ask first (only what you can't infer)
- A sector/region scan or a list of companies (customers, suppliers, borrowers)?
- Window. Default: 30 days for a scan, 90 days for a list.

## Before you run
- Window or size missing? Ask once: one multiple-choice question, recommended option first (e.g. "Last 30 days
  (Recommended)", "Fast, 50 rows (Recommended)"). Skip it when the user gave both or said "just run it".
- Standard/max, more than 20 companies or keep_updated: repeat the call with `dry_run=true` first (free) and show
  its time and cost in that question.
- Set up a monitor only when the user wants this regularly ("every week", "keep me posted"); not on one-off asks.
- While it runs, keep calling `get_research(run_id, wait_seconds=300)`; if you must stop first, say it is still
  running and ask the user to say "refresh".

## Run
- **Sector or region scan:** `start_research(query="Bankruptcy filings, insolvencies, restructurings, missed debt payments and going-concern warnings by <sector> companies in <region> since <date>: company, event type, court or process, debt amount, date", mode="fast", max_rows=100)`,
  then `get_research(run_id=…, wait_seconds=300)`.
- **Company list:** `start_research(companies=[…] or company_list_id=…, query="bankruptcy, insolvency, restructuring, default, missed payment, going concern, downgrade, layoffs, plant closure", lookback_days=90)`.
- **Spot check one name:** `search_news(query="<Company> bankruptcy OR insolvency OR restructuring OR default", window="30d")`,
  plus `list_articles(query="\"<Company>\" AND (bankruptcy OR insolvency OR \"Chapter 11\" OR administration OR restructuring)", from="<12 months ago>", search_in=["title"])`.
- Local-language terms matter: insolvenza, Insolvenz, faillite, concurso, recuperação judicial.

## Deliver
| Date | Company | Signal (filing, default, warning, downgrade…) | Detail | Source |
Then a risk ranking: confirmed filings first, then hard signals (missed payments), then soft signals (warnings, layoffs).

## Quality bar
- Show at most 25 rows inline (most important or newest first) and say how many there are; `export_research` gives the full table as a file.
- Separate confirmed events from reports and rumours; say which.
- Match the exact legal entity; a subsidiary's filing is not the parent's.
- No credit advice; report the signals.

## Keep it running
`create_monitor(company_list_id=…, query="bankruptcy, insolvency, restructuring, default", schedule={"every":"day","at":"07:00"})`.

## Done when
Every company in scope is marked "signal found" with sources or "nothing found in <window>".
