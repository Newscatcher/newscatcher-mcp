---
name: recalls-and-safety
description: "Use when the user wants product recalls, safety warnings, regulatory alerts or quality incidents — food, drugs, medical devices, vehicles, consumer products — by company, product category or country, over a period; for quality, regulatory affairs, supply chain or brand-risk work. Builds a recall table from the news with the NewsCatcher research agent."
---

# Recalls and safety incidents

Recalls and safety alerts with product, company, scale, reason and source.

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
1. `start_research(query="<Category> recalls and safety warnings announced in <country> since <date>, with company, product, units or lots affected, hazard, regulator (e.g. FDA, NHTSA, RAPEX) and recall date", mode="fast", max_rows=100)`.
2. `get_research(run_id, wait_seconds=300)`; `export_research` for the file.
3. One company or product, every mention: `list_articles(query="\"<Company>\" AND (recall OR recalled OR \"safety warning\")", from="12 months ago")`.
4. `create_monitor(from_run_id=run_id)` for new recalls.

## Deliver
Table: date · company · product · units/lots · hazard · regulator · status · source; then the largest recalls and
recurring hazards.

## Quality bar
- Show at most 25 rows inline (most important or newest first) and say how many there are; `export_research` gives the full table as a file.
- Regulator notices beat secondary reports when both exist; keep both links if useful.
- Separate recalls from lawsuits and from warnings without a recall.

## Done when
Every recall in scope has a row with a source and the hazard stated.
