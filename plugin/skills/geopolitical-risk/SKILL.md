---
name: geopolitical-risk
description: "Use when the user wants geopolitical or country risk news — conflicts, sanctions, elections, coups, protests, trade restrictions, tariffs, export controls, nationalisations, security incidents — for a country, region or trade route, for travel, operations, investment or supply-chain decisions. Produces a dated country risk brief from NewsCatcher, using local-language sources too."
---

# Geopolitical risk brief

What changed in a country or region that affects people, operations or trade, with local sources.

Runs on the NewsCatcher MCP tools (`search_news`, `count_articles`, `start_research`, `create_monitor`). If missing,
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
1. Main developments: `search_news(query="<country> political OR security OR sanctions OR protests OR election OR tariffs", window="7d", group="story", effort="high", limit=20)`.
2. Local view: the same with `countries=["<CC>"]` and/or `languages=[<local language>]` (results come back with English
   titles and summaries).
3. Event table for longer periods: `start_research(query="Political, security and trade events affecting businesses in <country> since <date>: protests, strikes, sanctions, tariffs, export controls, elections, government changes, security incidents, with date, type, location and source", mode="fast")`.
4. Escalation signal: `count_articles(queries=["\"<country>\" AND (protest OR clashes OR sanctions)"], from=<30 days ago>, interval="day")`.
5. Keep watch: `create_monitor(from_run_id=run_id, schedule={every:"day"})`.

## Deliver
- Situation in 3 lines; key developments (dated, sourced) by theme: politics, security, economy/trade, social unrest.
- What it means for the user's interest (operations, travel, supply chain), stated as reported implications.
- Watch list: scheduled elections, deadlines, sanctions reviews.

## Quality bar
- Show at most 25 rows inline (most important or newest first) and say how many there are; `export_research` gives the full table as a file.
- Local and international sources both, where available; label state media.
- Casualty and protest numbers as reported, with the source.

## Done when
The user has a current, sourced picture of the country risk and what to watch.
