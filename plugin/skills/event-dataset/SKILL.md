---
name: event-dataset
description: "Use when the user wants a table, list, spreadsheet or dataset of real-world events from the news — \"all X since Y\", deals, incidents, announcements, appointments, recalls, lawsuits, openings, closures, protests, contracts, any repeated event type — with one row per event and a source link. Runs the NewsCatcher research agent, picks the mode, checks the rows and exports the table."
---

# Event dataset

A verified table built from the news: one row per event, the columns the question needs, a source link per row.

Runs on the NewsCatcher MCP tools (`start_research`, `get_research`, `export_research`). If missing, see the
`newscatcher` skill.

## Defaults (say them in your first line)
- What counts as a row, the scope and the window come from the request ("this year" = Jan 1 to today). Missing the
  event type altogether? Ask and stop.
- Size: 50 rows in fast mode (3–10 minutes, about 1,000 credits). That is also the size when the user can't be
  asked, even for "every" or "all": run 50 and say that more rows (100–200) or a deeper mode find more.
- More rows than 50, or standard or max mode: show the cost with `dry_run=true` and wait for the user's OK first.

## Write the query
One sentence: **event + scope + window + columns**, describing events, not coverage.
- Good: "Vehicle recalls announced by car makers in the US between September 1 and November 5, 2026, with maker,
  model, number of vehicles, reason, recall date and source."
- Not "news articles about recalls"; not "car news". Several event types: several runs (cleaner columns).
- `dry_run=true` also flags a missing window or coverage-style wording, for free.

## Run
1. `start_research(query=<sentence>, mode="fast", max_rows=50)` (or 100, as above).
2. `get_research(run_id, wait_seconds=300)` until it finishes; if you must stop first, give the run id and ask the user
   to say "refresh". It shows 25 rows; page with `rows_offset` to see them all.
3. Check the rows (below). Then `get_research(run_id, wait_seconds=0, exclude_rows=[<# left out>], sort="newest")`:
   the table and the counts line now cover only the kept rows; use those numbers. Too few rows: rephrase (wider window
   or scope) or use `mode="standard"`.
4. Export: `export_research(run_id, file_format="csv", exclude_rows=[<# of duplicate or out-of-scope rows>])` so the
   file holds only the checked rows (xlsx works when nothing is excluded); give the file path.

## Check the rows
- Report plainly: only what the tool results say. No added causes, motives or labels ("main driver", "full licence",
  "positive tone"); if you give your own read, mark it as your read.
- A number appears only if a tool printed it or you counted it from rows you show; don't recompute a total a tool gave.
- Dates inside the window (event dates, not only publication dates); drop and count the others.
- One row per event: exclude a row as a duplicate only when it clearly describes the same event as another (same
  entity, date and detail); keep the better-sourced one. If you aren't sure, keep both and say so.
- In scope only: exclude rows clearly outside the event type, geography or window by their #, and count them.
  When a row's fit is unclear (e.g. a proposal when the user asked for construction announcements), keep it and mark
  it "(stage unclear)".
- Keep the facts as the rows give them (names, models, numbers, dates); you may shorten long text.
- get_research numbers every row (#); page with `rows_offset` to check them all before exporting.
- Every row has a source link. When the rows also carry a headline, title or summary column, show 2–3 checks, each
  as "#<n>: the row says <cell>; its headline says <text>". When they don't, write "rows carry source links but no
  headline to compare" and claim no checks.

## Deliver
1. First line: what the table covers (scope, window), rows kept, rows dropped and why.
2. The file path (when exported) and up to 10 kept rows inline, newest first (get_research with `sort="newest"`), with
   the key columns and the source link.
   The summary line quotes the "Counts over all N rows shown" line of the kept rows.
3. A one-line summary from the "Counts over all N rows" line of get_research ("38 recalls; Ford leads with 9").
4. What it may miss: a fast run samples big topics; thin coverage, non-English sources and small events. Next steps:
   more rows, `mode="standard"`, or a monitor with `create_monitor(from_run_id=run_id)` if the user wants it kept current.

## Before you send
Check each line; fix the answer where one fails.
- [ ] The first line gives scope, window, rows kept and rows dropped with the reason.
- [ ] Rows shown are newest first, facts as in the rows, each with a source link.
- [ ] The rows you checked against their sources are named by #.
- [ ] The file path is given when you exported; excluded rows were passed as exclude_rows.

## Done when
The table answers the question, the rows are checked, and the user has the file and knows what it covers.
