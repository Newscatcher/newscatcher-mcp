---
name: partnerships-tracker
description: "Use when the user wants strategic partnerships, alliances, joint ventures, distribution or reseller deals, integrations and co-marketing agreements for a company, its competitors or a sector; for corporate development, partner teams, sales and analysts. Tracks partnership announcements from the news with NewsCatcher."
---

# Partnerships tracker

Who partnered with whom, to do what, with a source per announcement.

Runs on the NewsCatcher MCP tools (see the `newscatcher` skill for setup, costs and errors).

## Ask first (only what you can't infer)
- The companies (yours and competitors) or the sector, and the window. Default: 90 days for companies, 30 for a sector.

## Before you run
- Window or size missing? Ask once: one multiple-choice question, recommended option first (e.g. "Last 30 days
  (Recommended)", "Fast, 50 rows (Recommended)"). Skip it when the user gave both or said "just run it".
- Standard/max, more than 20 companies or keep_updated: repeat the call with `dry_run=true` first (free) and show
  its time and cost in that question.
- Set up a monitor only when the user wants this regularly ("every week", "keep me posted"); not on one-off asks.
- While it runs, keep calling `get_research(run_id, wait_seconds=300)`; if you must stop first, say it is still
  running and ask the user to say "refresh".

## Run
- **Companies:** `start_research(companies=[…] or company_list_id=…, query="partnerships, alliances, joint ventures, distribution deals, integrations", lookback_days=90)`,
  then `get_research(run_id=…, wait_seconds=300)`.
- **Sector:** `start_research(query="Strategic partnerships and joint ventures announced by <sector> companies since <date>: partners, type, purpose, region, date", mode="fast", max_rows=100)`.
- **Quick look at one company:** `search_news(query="<Company> partnership OR partners with OR alliance OR joint venture", window="30d", group="story")`.
- Density by company (optional): `count_articles(queries=["\"<A>\" AND (partnership OR \"partners with\")", "\"<B>\" AND (partnership OR \"partners with\")"], from="<90 days ago>", interval="month")`.

## Deliver
| Date | Company | Partner | Type | What it covers | Source |
Then a partner map in words: who partners most, overlaps with competitors, and notable new categories.

## Quality bar
- Show at most 25 rows inline (most important or newest first) and say how many there are; `export_research` gives the full table as a file.
- Announced partnerships only; "in talks" is labelled as a report.
- One row per deal, not per article.
- Name both parties as the announcement does.

## Keep it running
`create_monitor(company_list_id=…, query="partnerships, alliances, joint ventures", schedule={"every":"week"})`.

## Done when
Each company or the sector has its partnership announcements listed with sources, or "none found".
