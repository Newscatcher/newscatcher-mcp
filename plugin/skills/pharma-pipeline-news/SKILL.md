---
name: pharma-pipeline-news
description: "Use when the user wants drug and biotech pipeline news: FDA, EMA or other regulator decisions, approvals and rejections, clinical trial readouts, safety signals, recalls, licensing deals and patent fights for a company, drug, indication or therapy area. Reports sourced pipeline news with NewsCatcher; no medical or investment advice."
---

# Pharma pipeline news

Regulatory decisions, trial results and deals for your drugs or companies, each with a source.

Runs on the NewsCatcher MCP tools (see the `newscatcher` skill for setup, costs and errors).

## Ask first (only what you can't infer)
- Companies, drug names (brand and generic), indications or a therapy area, and the window. Default: 30 days.

## Before you run
- Window or size missing? Ask once: one multiple-choice question, recommended option first (e.g. "Last 30 days
  (Recommended)", "Fast, 50 rows (Recommended)"). Skip it when the user gave both or said "just run it".
- Standard/max, more than 20 companies or keep_updated: repeat the call with `dry_run=true` first (free) and show
  its time and cost in that question.
- Set up a monitor only when the user wants this regularly ("every week", "keep me posted"); not on one-off asks.
- While it runs, keep calling `get_research(run_id, wait_seconds=300)`; if you must stop first, say it is still
  running and ask the user to say "refresh".

## Run
- **Therapy area or sector:** `start_research(query="Regulatory decisions, clinical trial readouts and licensing deals in <therapy area> since <date>: company, drug, indication, event (approval, rejection, phase result, deal), outcome, date", mode="fast", max_rows=100)`,
  then `get_research(run_id=…, wait_seconds=300)`.
- **Companies:** `start_research(companies=[…], query="FDA EMA approvals, clinical trial results, safety, recalls, licensing deals", lookback_days=30)`.
- **One drug:** `search_news(query="<drug brand> <generic> trial OR FDA OR approval", window="30d", group="story")`, then
  `list_articles(query="(\"<brand>\" OR \"<generic>\") AND (FDA OR EMA OR trial OR approval OR recall)", from="<12 months ago>")`.
- Safety and recalls: see the `recalls-and-safety` skill.

## Deliver
| Date | Company | Drug | Indication | Event | Outcome (as reported) | Source |
Then what changed this period and upcoming decision dates the coverage mentions.

## Quality bar
- Show at most 25 rows inline (most important or newest first) and say how many there are; `export_research` gives the full table as a file.
- Trial results as the company or journal reported them (endpoint met or not); don't interpret efficacy.
- Approval, recommendation (e.g. advisory committee) and acceptance of filing are different; label each.
- No medical advice and no investment views.

## Keep it running
`create_monitor(company_list_id=…, query="FDA, EMA, trial results, approvals, safety", schedule={"every":"day","at":"08:00"})`.

## Done when
Each drug or company in scope has its events listed with sources, or "nothing reported in <window>".
