---
name: competitor-intelligence
description: "Use when the user wants competitive intelligence — what competitors launched, announced, raised, hired, lost or were criticised for; competitor news digests; share of voice against competitors; or ongoing competitor monitoring. Compares the user's company with its competitors using NewsCatcher company research, counts and news search."
---

# Competitor intelligence

What each competitor did recently, how much attention they get versus you, and what it means.

Runs on the NewsCatcher MCP tools (`start_research`, `get_research`, `count_articles`, `search_news`, `create_monitor`).
If missing, see the `newscatcher` skill.

## Ask first (only what's missing)
- The user's company and 2–8 competitors, as domains.
- Window (default 30 days) and focus (launches, pricing, funding, hires, partnerships, customers, outages, legal).

## Before you run
- Window or size missing? Ask once: one multiple-choice question, recommended option first (e.g. "Last 30 days
  (Recommended)", "Fast, 50 rows (Recommended)"). Skip it when the user gave both or said "just run it".
- Standard/max, more than 20 companies or keep_updated: repeat the call with `dry_run=true` first (free) and show
  its time and cost in that question.
- Set up a monitor only when the user wants this regularly ("every week", "keep me posted"); not on one-off asks.
- While it runs, keep calling `get_research(run_id, wait_seconds=300)`; if you must stop first, say it is still
  running and ask the user to say "refresh".

## Run
1. Company news: `start_research(companies=[you, competitors…], query=<focus or omit>, lookback_days=30, wait_seconds=300)`;
   `get_research` until done. One row per story with type and importance.
2. Share of voice: `count_articles(queries=["\"You\"", "\"Rival A\"", …], from=<window start>, interval="week")`.
   Use precise boolean queries for ambiguous names (`"Notion" AND (app OR software OR workspace)`).
3. Themes across the market: `search_news(query="<category> launches OR pricing OR funding", window="30d", group="story")`.

## Report file (when export_research is available)
On a local setup build an HTML report (scoreboard, story types, share of voice, every story with its link) from saved
files; the chat answer then gives the highlights and the path. One folder, e.g. `newscatcher-exports/competitors-<date>/` (below: `<dir>`).
1. After the company run: `export_research(run_id=…, file_format="json", path="<dir>/companies.json")`.
2. The share-of-voice count with `save_as="json", path="<dir>/sov.json"` added.
3. Optional market themes: the search from Run with `save_as="json", path="<dir>/market.json"` added.
4. Write the moves that matter, the "so what" and the gaps to `<dir>/notes.md` (facts from the rows only).
5. Run `node <this skill's base directory>/scripts/render-report.mjs --title "Competitors: <you> vs <rivals>" --subtitle "<window>"
   --rows "Company news=<dir>/companies.json" --counts "Share of voice=<dir>/sov.json" --stories "Market themes=<dir>/market.json"
   --notes <dir>/notes.md --out <dir>/report.html`. If you can't write files, pass the notes on stdin instead: `--notes -` followed by a quoted heredoc (`<<'EOF'` … `EOF`).
6. In chat: the summary lines it prints and the report path; open the file. Without export_research, deliver as below.

## Deliver
- **Scoreboard**: per company — stories, top story types, share of voice %, momentum (week over week).
- **Moves that matter**: dated competitor actions with links, and a "so what" for the user.
- **Gaps and openings**: what competitors are criticised for, what they didn't do.
- If the user wants to keep watching: `create_monitor(companies=[…competitors], query=<focus>, schedule={every:"week"})`.

## Quality bar
- Show at most 25 rows inline (most important or newest first) and say how many there are; `export_research` gives the full table as a file.
- Same window and method for every company; say if a name's counts include namesakes.
- Facts from coverage only; label opinion pieces and rumours.

## Done when
The user can say what each competitor did this month and where they stand on attention, with sources.
