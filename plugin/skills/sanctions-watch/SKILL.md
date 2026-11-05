---
name: sanctions-watch
description: "Use when the user needs news on sanctions, export controls, entity-list additions, asset freezes, designations or sanctions violations touching named companies, people, countries or sectors; for compliance, trade, supply chain or investment screening. Collects sourced sanctions news with NewsCatcher; it does not replace official sanctions lists."
---

# Sanctions watch

News on sanctions and export controls that touch your entities or sectors, each with a source.

Runs on the NewsCatcher MCP tools (see the `newscatcher` skill for setup, costs and errors).

## Ask first (only what you can't infer)
- What to watch: named entities (companies, people, vessels), countries, or sectors (chips, energy, shipping).
- Window. Default: 30 days.

## Before you run
- Window or size missing? Ask once: one multiple-choice question, recommended option first (e.g. "Last 30 days
  (Recommended)", "Fast, 50 rows (Recommended)"). Skip it when the user gave both or said "just run it".
- Standard/max, more than 20 companies or keep_updated: repeat the call with `dry_run=true` first (free) and show
  its time and cost in that question.
- Set up a monitor only when the user wants this regularly ("every week", "keep me posted"); not on one-off asks.
- While it runs, keep calling `get_research(run_id, wait_seconds=300)`; if you must stop first, say it is still
  running and ask the user to say "refresh".

## Run
- **Sanctions actions in a scope:** `start_research(query="New sanctions, export controls, entity list additions and designations announced since <date> affecting <country/sector>: authority (OFAC, EU, UK OFSI, BIS…), target, measure, date", mode="fast", max_rows=100)`,
  then `get_research(run_id=…, wait_seconds=300)`.
- **Named entities:** per entity `search_news(query="\"<Entity>\" sanctions OR \"export controls\" OR \"entity list\" OR designated", window="30d")`,
  and `list_articles(query="\"<Entity>\" AND (sanction OR sanctions OR sanctioned OR \"entity list\" OR \"export ban\")", from="<12 months ago>")`.
  Many entities: `start_research(companies=[…], query="sanctions, export controls, designations, violations")`.
- Include local-language and transliterated names for non-Latin entities.

## Deliver
| Date | Authority | Target | Measure | Relevance to you | Source |
Then: what is new this period, and open items (proposed but not adopted measures).

## Quality bar
- Show at most 25 rows inline (most important or newest first) and say how many there are; `export_research` gives the full table as a file.
- News is a signal, not a determination: always point to the official list (OFAC SDN, EU consolidated list, UK
  sanctions list) for confirmation.
- Proposed, announced and in-force are different; label each.
- Exact-name matches only; mark possible matches as "possible match, verify".

## Keep it running
`create_monitor(companies=[…], query="sanctions, export controls, designations", schedule={"every":"day"})`, or
`start_research(query=…, keep_updated=true)` for a scope-wide feed.

## Done when
Each entity or scope has its sanctions news listed or "nothing found in <window>", with the official-list caveat.
