---
name: supplier-risk
description: "Use when the user wants to monitor suppliers, vendors, logistics partners or a supply chain for disruptions — strikes, plant fires, outages, bankruptcies, sanctions, recalls, cyberattacks, natural disasters, port closures, shortages — or to assess third-party risk. Screens a supplier list with NewsCatcher company research, keeps a monitor on it and flags region-wide disruptions."
---

# Supplier risk

Disruptions at your suppliers and in the places they operate, as they are reported.

Runs on the NewsCatcher MCP tools (`save_company_list`, `start_research`, `get_research`, `create_monitor`,
`get_monitor_updates`, `search_news`). If missing, see the `newscatcher` skill.

## Ask first (only what's missing)
- Supplier domains (or names + country), what they supply, critical sites/regions, and the risk types that matter.

## Before you run
- Window or size missing? Ask once: one multiple-choice question, recommended option first (e.g. "Last 30 days
  (Recommended)", "Fast, 50 rows (Recommended)"). Skip it when the user gave both or said "just run it".
- Standard/max, more than 20 companies or keep_updated: repeat the call with `dry_run=true` first (free) and show
  its time and cost in that question.
- Set up a monitor only when the user wants this regularly ("every week", "keep me posted"); not on one-off asks.
- While it runs, keep calling `get_research(run_id, wait_seconds=300)`; if you must stop first, say it is still
  running and ask the user to say "refresh".

## Run
1. `save_company_list(name="Suppliers", companies=[…])`; fix identities with `get_company_list`/`edit_company_list`.
2. Screen: `start_research(company_list_id=…, query="disruptions: strikes, fires, explosions, outages, bankruptcy, insolvency, layoffs, sanctions, recalls, cyberattacks, plant closures, shortages, lawsuits", lookback_days=60)`; `get_research(run_id, wait_seconds=300)`.
3. Places, not just companies: `search_news(query="<region or port> strike OR closure OR flood OR earthquake OR shortage", window="3d", group="story")` for each critical region.
4. Monitor: `create_monitor(company_list_id=…, query=<same as step 2>, schedule={every:"day", at:"08:00", tz:<tz>})`;
   review deliveries with `get_monitor_updates`.

## Deliver
Risk register: supplier · event · date · severity (high: production stopped, insolvency, sanctions; medium: strike
threat, recall, lawsuit; low: rumours, minor incidents) · source · suggested action (check stock, contact supplier,
activate second source).

## Quality bar
- Show at most 25 rows inline (most important or newest first) and say how many there are; `export_research` gives the full table as a file.
- Severity from what is reported, not guessed impact; say when the effect on the user's orders is unknown.
- Same-name companies in other countries are a common false positive: check the domain/country.

## Done when
Every supplier has a status (incident / nothing reported), incidents are rated and sourced, and the monitor is on.
