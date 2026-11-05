---
name: commodity-news
description: "Use when the user wants news that moves commodities: oil, gas, LNG, metals, grains, softs or power; supply disruptions, OPEC decisions, export bans, strikes, weather, inventories and policy; a daily commodity brief or attention trends. Collects sourced commodity news and volume trends with NewsCatcher; no trading advice."
---

# Commodity news

What is moving a commodity in the news, with sources and attention trends. No trading advice.

Runs on the NewsCatcher MCP tools (see the `newscatcher` skill for setup, costs and errors).

## Ask first (only what you can't infer)
- The commodities and regions, the window (default: last 24 hours for a brief, 30 days for a review).

## Before you run
- Window or size missing? Ask once: one multiple-choice question, recommended option first (e.g. "Last 30 days
  (Recommended)", "Fast, 50 rows (Recommended)"). Skip it when the user gave both or said "just run it".
- Standard/max, more than 20 companies or keep_updated: repeat the call with `dry_run=true` first (free) and show
  its time and cost in that question.
- Set up a monitor only when the user wants this regularly ("every week", "keep me posted"); not on one-off asks.
- While it runs, keep calling `get_research(run_id, wait_seconds=300)`; if you must stop first, say it is still
  running and ask the user to say "refresh".

## Run
1. Brief: per commodity `search_news(query="<commodity> supply OR prices OR exports OR production", window="1d", group="story", min_newsrooms=3)`.
   Add producer-country languages where the news breaks first (e.g. `languages=["es"]` for Chilean copper, ["ru"] or ["ar"] for oil).
2. Specific drivers: `search_news(query="OPEC+ output decision", window="7d")`, `search_news(query="<crop> export ban", window="7d")`,
   `search_news(query="<mine/port> strike OR outage", window="7d")`.
3. Attention: `count_articles(queries=["\"<commodity>\" AND (shortage OR disruption)", "\"<commodity>\" AND (surplus OR glut)"], from="<30 days ago>", interval="day")`.
4. Event table for a period: `start_research(query="Supply disruptions affecting <commodity> since <date>: event, location, volume affected, duration, date", mode="fast")`.

## Deliver
Per commodity: 3–5 bullets (driver · what happened · where · source), then "watch next" items the coverage mentions,
and the attention trend if counted.

## Quality bar
- Show at most 25 rows inline (most important or newest first) and say how many there are; `export_research` gives the full table as a file.
- Prices and volumes exactly as reported, with units and dates.
- Separate confirmed events (an announced cut) from forecasts and analyst views.
- No price predictions or trade ideas.

## Keep it running
`start_research(query=…, keep_updated={"every":"day","at":"06:00"})` for a disruption log.

## Done when
Each commodity has today's drivers with sources, or "no significant news".
