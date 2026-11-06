---
name: weekly-digest
description: "Use when the user wants a recurring newsletter-style digest: a weekly or daily round-up on a topic, industry, competitor set or portfolio, with the top stories, what changed and links; set up once, delivered on a schedule. Builds the digest with NewsCatcher search and monitors and a fixed digest template."
---

# Weekly digest

A consistent round-up on a topic or company set, same structure every week, every item linked.

Runs on the NewsCatcher MCP tools (see the `newscatcher` skill for setup, costs and errors).

## Ask first (only what you can't infer)
- The subject (topic, industry, or companies), the audience, the cadence (weekly default, daily) and the length
  (default: 5–10 items).

## Before you run
- Window or size missing? Ask once: one multiple-choice question, recommended option first (e.g. "Last 30 days
  (Recommended)", "Fast, 50 rows (Recommended)"). Skip it when the user gave both or said "just run it".
- Standard/max, more than 20 companies or keep_updated: repeat the call with `dry_run=true` first (free) and show
  its time and cost in that question.
- Set up a monitor only when the user wants this regularly ("every week", "keep me posted"); not on one-off asks.
- While it runs, keep calling `get_research(run_id, wait_seconds=300)`; if you must stop first, say it is still
  running and ask the user to say "refresh".

## Run
1. Topic digest: `search_news(query="<topic>", window="7d", group="story", min_newsrooms=3, limit=20)` and 1–3 more
   searches for sub-themes. Pick the stories with the most newsrooms and the most consequence.
2. Company digest: `start_research(company_list_id=… or companies=[…], query="<what matters>", lookback_days=7)`, then
   `get_research(run_id=…, wait_seconds=300)`.
3. Numbers line (optional): `count_articles(queries=[…], from="<14 days ago>", interval="week")` for "coverage up/down vs
   last week".
4. Set up the schedule so next week's digest is one call:
   - companies: `create_monitor(company_list_id=…, query=…, schedule={"every":"week","weekday":0,"at":"08:00","tz":"<user tz>"})`,
     then each week `get_monitor_updates(monitor_id=…)`.
   - topic: `start_research(query="<topic> news since <date>", keep_updated={"every":"week","weekday":0,"at":"08:00"})`.

## Report file (when search_news offers save_as)
When the user wants the digest as a page or file to share, build it as HTML. One folder per issue, e.g.
`newscatcher-exports/<subject>-<date>/` (below: `<dir>`).
- Add `save_as="json", path="<dir>/<theme>.json"` to each search; company digest:
  `export_research(run_id=…, file_format="json", path="<dir>/companies.json")`; numbers:
  `count_articles(…, save_as="json", path="<dir>/volume.json")`.
- Write the digest text (the template below) to `<dir>/notes.md`, then run `node <this skill's base directory>/scripts/render-report.mjs
  --title "<Subject>, week of <date>" --notes <dir>/notes.md --stories "<Theme>=<dir>/<theme>.json" (one per theme)
  --rows "Company news=<dir>/companies.json" --counts "Coverage=<dir>/volume.json" --out <dir>/digest.html`. If you can't write files, pass the notes on stdin instead: `--notes -` followed by a quoted heredoc (`<<'EOF'` … `EOF`).
- A story shown in one section is left out of later ones automatically. Post the digest text in chat as well, with
  the file path.

## Deliver (template)
```
<Subject> — week of <date>
The week in one line: …
Top stories
1. <Headline-style summary> — <why it matters>. <Outlet>, <date>. <link>
…
Also notable: 3–5 one-liners with links
By the numbers: <counts or trend, if measured>
Next week: scheduled events the coverage mentions
```

## Quality bar
- Show at most 25 rows inline (most important or newest first) and say how many there are; `export_research` gives the full table as a file.
- Each item is a distinct story (use story ids to avoid repeats) with a link.
- "Why it matters" is one sentence and tied to the audience.
- Same sections every issue; say "quiet week" rather than padding.

## Done when
This week's digest is delivered in the template and the schedule exists for the next ones.
