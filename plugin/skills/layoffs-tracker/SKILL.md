---
name: layoffs-tracker
description: "Use when the user wants layoffs, job cuts, restructurings, hiring freezes or plant closures — which companies, how many jobs, where, when — for an industry, region or company list; for labour-market research, HR, investors, journalists or sales. Builds a layoffs table from the news with the NewsCatcher research agent."
---

# Layoffs tracker

Who is cutting jobs, how many, where and when, with a source for each.

Runs on the NewsCatcher MCP tools (`start_research`, `get_research`, `export_research`, `count_articles`,
`create_monitor`). If missing, see the `newscatcher` skill.

## Before you run
- Window or size missing? Ask once: one multiple-choice question, recommended option first (e.g. "Last 30 days
  (Recommended)", "Fast, 50 rows (Recommended)"). Skip it when the user gave both or said "just run it".
- Standard/max, more than 20 companies or keep_updated: repeat the call with `dry_run=true` first (free) and show
  its time and cost in that question.
- Set up a monitor only when the user wants this regularly ("every week", "keep me posted"); not on one-off asks.
- While it runs, keep calling `get_research(run_id, wait_seconds=300)`; if you must stop first, say it is still
  running and ask the user to say "refresh".

## Run
1. `start_research(query="Layoffs and job cuts announced by <sector> companies in <geography> since <date>, with company, number of jobs cut, share of workforce, locations, reason and announcement date", mode="fast", max_rows=100)`.
2. `get_research(run_id, wait_seconds=300)`; `export_research` for the file.
3. Trend (optional): `count_articles(queries=["(layoffs OR \"job cuts\" OR \"cutting jobs\") AND <sector term>"], from=<90 days ago>, interval="week")`.
4. For a company list: `start_research(company_list_id=…, query="layoffs, job cuts, restructuring, hiring freeze")`.

## Deliver
Table: date · company · jobs cut (number or %, as reported) · locations · reason · source. Then the total of
disclosed cuts, the biggest cuts, and sectors or regions that stand out.

## Quality bar
- Show at most 25 rows inline (most important or newest first) and say how many there are; `export_research` gives the full table as a file.
- Use the announced number; "about", "up to" stay as reported. Don't add percentages and headcounts together.
- One row per announcement; a later second round is a new row.

## Done when
The table covers the window and scope with sources, and totals use only disclosed numbers.
