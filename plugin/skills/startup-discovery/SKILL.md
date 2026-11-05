---
name: startup-discovery
description: "Use when the user wants to find startups or emerging companies in a space from the news: who raised money, launched, won customers or got press for a technology, market or region; for VC sourcing, corporate development, partnerships or competitive scans. Builds a startup list with sources and can save it as a NewsCatcher company list to watch."
---

# Startup discovery

Companies in a space that the news is talking about, with why they surfaced, ready to watch.

Runs on the NewsCatcher MCP tools (see the `newscatcher` skill for setup, costs and errors).

## Ask first (only what you can't infer)
- The space (technology, market), region, stage (pre-seed to growth) and window. Default: 90 days.
- What counts as a hit: raised money, launched, notable customer, or any coverage.

## Before you run
- Window or size missing? Ask once: one multiple-choice question, recommended option first (e.g. "Last 30 days
  (Recommended)", "Fast, 50 rows (Recommended)"). Skip it when the user gave both or said "just run it".
- Standard/max, more than 20 companies or keep_updated: repeat the call with `dry_run=true` first (free) and show
  its time and cost in that question.
- Set up a monitor only when the user wants this regularly ("every week", "keep me posted"); not on one-off asks.
- While it runs, keep calling `get_research(run_id, wait_seconds=300)`; if you must stop first, say it is still
  running and ask the user to say "refresh".

## Run
1. `start_research(query="Startups in <space> in <region> that raised funding, launched products or announced major customers since <date>: company, website domain, what they do, round and amount, investors, date", mode="fast", max_rows=100)`,
   then `get_research(run_id=…, wait_seconds=300)`.
2. Widen recall with news searches using the words founders use: `search_news(query="<space> startup raises", window="30d", limit=30)`,
   `search_news(query="<space> seed round", window="30d")`; add `countries=[…]` and local languages for regional scans.
3. De-duplicate by domain and drop large incumbents unless asked.
4. Save the shortlist: `save_company_list(companies=["domain1.com", …], name="<space> startups")`, or after a company run
   `save_company_list(from_run_id=…)`.

## Deliver
| Company | Domain | What they do | Why it surfaced (round, launch, customer) | Date | Source |
Then 3–5 bullets on patterns: hot sub-segments, active investors, regions.

## Quality bar
- Show at most 25 rows inline (most important or newest first) and say how many there are; `export_research` gives the full table as a file.
- Every company has at least one sourced news item; no companies from memory.
- Domains must belong to the company in the article; leave blank when unsure.
- Amounts as reported, with currency.

## Keep it running
`create_monitor(company_list_id=…, query="funding, launches, customers, hires", schedule={"every":"week"})`, and rerun
discovery monthly to add new names with `save_company_list(list_id=…, companies=[…])`.

## Done when
The list covers the space and window with sources per company and is saved for watching if the user wants it.
