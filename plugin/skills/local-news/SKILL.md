---
name: local-news
description: "Use when the user wants news about a city, county, state or region, or local coverage of an issue: local politics, development and zoning, closures and openings, crime and safety, weather events, local businesses; for local government, real estate, retail, franchise or community teams. Finds local outlets first with NewsCatcher's country, language and source filters."
---

# Local news

What local outlets report about a place or an issue there, with links.

Runs on the NewsCatcher MCP tools (see the `newscatcher` skill for setup, costs and errors).

## Ask first (only what you can't infer)
- The place (city plus state/region and country, to avoid namesakes like Paris, Texas), topics of interest, and the
  window. Default: 7 days.

## Before you run
- Window or size missing? Ask once: one multiple-choice question, recommended option first (e.g. "Last 30 days
  (Recommended)", "Fast, 50 rows (Recommended)"). Skip it when the user gave both or said "just run it".
- Standard/max, more than 20 companies or keep_updated: repeat the call with `dry_run=true` first (free) and show
  its time and cost in that question.
- Set up a monitor only when the user wants this regularly ("every week", "keep me posted"); not on one-off asks.
- While it runs, keep calling `get_research(run_id, wait_seconds=300)`; if you must stop first, say it is still
  running and ask the user to say "refresh".

## Run
1. `search_news(query="<City> <topic>", countries=["<CC>"], window="7d", limit=30)`; in non-English places use the local
   language and name (`languages=["it"]`, "Comune di Bologna").
2. Pin the local press: note the local outlets that appear and rerun with `sources=["<local outlet domains>"]`.
3. Exact place mentions or older items: `list_articles(query="\"<City>\" AND (<topic words>)", countries=["<CC>"], from="<start>", search_in=["title"], page_size=50)`.
4. Activity trend (optional): `count_articles(queries=["\"<City>\" AND (<topic words>)"], from="<90 days ago>", countries=["<CC>"], interval="week")`.

## Deliver
Grouped by topic: bullets with outlet, date, one line, link. Name the local outlets you relied on, and say when only
national outlets covered something.

## Quality bar
- Show at most 25 rows inline (most important or newest first) and say how many there are; `export_research` gives the full table as a file.
- Check every item is about the right place (state/region in the article).
- Local outlets first; national pieces only when they add something.
- Mark single-source items.

## Keep it running
Rerun weekly with the same queries and source list, or `start_research(query="<topic> in <City> since <date>", keep_updated=true)`
for a dated log.

## Done when
Each topic has local items with links, or "no local coverage found in <window>".
