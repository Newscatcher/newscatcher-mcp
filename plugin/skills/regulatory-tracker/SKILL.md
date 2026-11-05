---
name: regulatory-tracker
description: "Use when the user wants regulatory and policy news — new laws, rules, guidance, enforcement actions, fines, investigations, approvals or bans by regulators (SEC, FTC, FDA, EU Commission, FCA, CMA, central banks…) in a sector or jurisdiction — for compliance, public affairs, legal or strategy teams. Builds a regulatory-actions table and briefing from NewsCatcher and keeps it updated."
---

# Regulatory tracker

What regulators decided, proposed or enforced, with dates, scope and sources.

Runs on the NewsCatcher MCP tools (`start_research`, `get_research`, `search_news`, `create_monitor`). If missing, see
the `newscatcher` skill.

## Before you run
- Window or size missing? Ask once: one multiple-choice question, recommended option first (e.g. "Last 30 days
  (Recommended)", "Fast, 50 rows (Recommended)"). Skip it when the user gave both or said "just run it".
- Standard/max, more than 20 companies or keep_updated: repeat the call with `dry_run=true` first (free) and show
  its time and cost in that question.
- Set up a monitor only when the user wants this regularly ("every week", "keep me posted"); not on one-off asks.
- While it runs, keep calling `get_research(run_id, wait_seconds=300)`; if you must stop first, say it is still
  running and ask the user to say "refresh".

## Run
1. Actions table: `start_research(query="Regulatory actions in <sector> in <jurisdiction> since <date>: new rules, proposed rules, guidance, enforcement actions, fines, investigations, approvals and bans, with regulator, action type, affected companies, amount if any and date", mode="fast", max_rows=100)`; use mode="standard" for a cited briefing.
2. `get_research(run_id, wait_seconds=300)`.
3. Fresh developments: `search_news(query="<regulator> <sector> rule OR fine OR investigation OR guidance", window="7d", group="story")`.
4. `create_monitor(from_run_id=run_id, schedule={every:"week"})`.

## Deliver
Table: date · regulator · action type (proposed / final rule / guidance / enforcement / fine / approval) · subject ·
companies · amount · status · source. Briefing: what changed, who is affected, deadlines and comment periods.

## Quality bar
- Show at most 25 rows inline (most important or newest first) and say how many there are; `export_research` gives the full table as a file.
- Proposed vs final vs in force; effective dates when reported.
- Link to the regulator's own notice when an article cites it.
- Not legal advice.

## Done when
Every action in scope is listed with type, status and source, and upcoming deadlines are called out.
