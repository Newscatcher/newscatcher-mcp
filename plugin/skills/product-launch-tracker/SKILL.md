---
name: product-launch-tracker
description: "Use when the user wants product launches, releases, feature announcements, new models or services — from competitors, a sector or a company list — over a period; for product marketing, competitive analysis and market research. Builds a launch table from the news with the NewsCatcher research agent, or a quick digest with news search."
---

# Product launch tracker

What was launched, by whom, when, and how it was received.

Runs on the NewsCatcher MCP tools (`start_research`, `get_research`, `search_news`, `get_story`). If missing, see the
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
- **Quick digest (a few companies, last weeks):** `search_news(query="<company> launches OR unveils OR announces new", window="30d", group="story")` per company; `get_story` on big launches for reception (newsroom count).
- **Table (a market):** `start_research(query="Product launches and major feature releases by <sector> companies since <date>, with company, product, category, launch date, pricing if reported and source", mode="fast", max_rows=100)`, then `get_research`.
- **Competitors on a schedule:** `create_monitor(companies=[…], query="product launches, new features, pricing changes")`.

## Deliver
Table: date · company · product · what is new · pricing (if reported) · coverage (newsrooms) · source. Then the
launches that got the most coverage and what they signal.

## Quality bar
- Show at most 25 rows inline (most important or newest first) and say how many there are; `export_research` gives the full table as a file.
- Launch = available or officially announced; teasers and leaks labelled.
- Coverage size from the story's newsroom count, not article copies.

## Done when
Launches in scope are listed with dates and sources, with the biggest ones called out.
