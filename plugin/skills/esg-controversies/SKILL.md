---
name: esg-controversies
description: "Use when the user wants ESG controversies or sustainability news for companies or a portfolio — environmental incidents, spills, emissions violations, labour and human-rights abuses, safety accidents, governance scandals, greenwashing claims, boycotts — for ESG research, responsible investing, compliance or reporting. Screens companies with NewsCatcher and classifies incidents by E, S and G."
---

# ESG controversies

Reported environmental, social and governance incidents per company, classified and sourced.

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
1. Portfolio screen: `start_research(companies=[…domains] or company_list_id=…, query="environmental incidents, pollution, spills, emissions violations, labour disputes, human rights abuses, worker safety accidents, discrimination lawsuits, bribery, governance scandals, greenwashing allegations, boycotts", lookback_days=180)`; `get_research(run_id, wait_seconds=300)`.
2. Exhaustive check per high-risk company: `list_articles(query="\"<Company>\" AND (spill OR pollution OR \"forced labour\" OR \"child labour\" OR greenwashing OR fatality OR bribery OR boycott)", from="12 months ago")`.
3. Keep watch: `create_monitor(company_list_id=…, query=<step 1 query>, schedule={every:"week"})`.

## Deliver
Per company: incidents table (date · category E/S/G · sub-type · description · status: alleged / investigated /
fined / settled · outlets · source) and a one-line assessment. Portfolio view: companies by number and severity of
incidents.

## Quality bar
- Show at most 25 rows inline (most important or newest first) and say how many there are; `export_research` gives the full table as a file.
- Allegations, investigations, fines and settlements are different statuses.
- Use reporting dates and event dates correctly; old incidents resurfacing in new articles keep their event date.
- Research support only; not an ESG rating.

## Done when
Each company has its incidents classified with sources, or an explicit "none reported in <window>".
