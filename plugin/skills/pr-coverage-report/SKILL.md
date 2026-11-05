---
name: pr-coverage-report
description: "Use when the user wants a PR or media coverage report — how a launch, announcement, campaign, crisis, report or executive got covered: number of articles and outlets, top-tier outlets, countries, languages, key messages picked up, headlines, reach over time. Produces a coverage report with exact counts and a list of clips from NewsCatcher."
---

# PR coverage report

How much coverage, where, in which outlets, saying what: exact numbers, a clip list and the method.

Runs on the NewsCatcher MCP tools (`list_articles`, `count_articles`, `search_news`, `get_story`). If missing, see the
`newscatcher` skill.

## First
- The announcement is unnamed ("our product launch")? Ask for the company and product names, the announcement date
  and the key messages, and stop. Don't search a guess.
- Window: the user's own window when they give one ("this week" = Monday to now, "last week" = the previous
  Monday–Sunday); otherwise from the announcement date to now. The only "first" claim allowed is get_story's earliest
  article (no "first wire" or "broke the news" claims). Key messages: what the user listed, else the announcement's main claims. Say the window and messages in
  your first line.

## Build the query
One boolean query for the clips: `"<Company>" AND ("<product or deal name>" OR <2–3 distinctive words>)`, matched in
headlines (`search_in=["title"]`) so clips are about the announcement. Check it once with
`list_articles(query=<Q>, from=<start>, search_in=["title"], page_size=10, sort="relevance")`: if more than two of the
ten are off topic, tighten the words (the deal's exact name, a required second term) and check again; count only
with a query whose check shows at most two off-topic clips. Under 10 matches in total, widen to
`search_in=["title_body"]` and check again. Use the same query and fields in every step below, and say which in the
method line.

## Run
1. Exact total: `list_articles(query=<Q>, from=<start>, count_only=true)`; original articles only: the same with
   `exclude_duplicates=true` (the difference is syndicated copies).
2. Outlets, countries, languages in one pass: `list_articles(query=<Q>, from=<start>, tally=["source","country","language"], tally_pages=10)`
   (counts up to 1,000 newest matches; gives the number of distinct outlets, countries and languages).
3. Tier-1: `list_articles(query=<Q>, from=<start>, search_in=<same fields>, top_sources="top 100 US", tally="source", tally_pages=10)`
   (or the main market, "top 100 GB"): its "distinct values" is the number of tier-1 outlets across every tier-1
   match, and each outlet comes with its latest clip and link. Use a latest clip as a tier-1 clip only when its
   headline is about the announcement; otherwise name the outlet without a clip.
4. Volume by day: `count_articles(queries=[<Q>], from=<start>, interval="day")`.
5. The main story: `search_news(query=<announcement in plain words>, window="7d", group="story", limit=10)` and
   `get_story(story_id)` on the matching story for its newsroom count and the first outlet to report.
6. Key messages: read the headlines and snippets from steps 2–3 and mark each message picked up (with example links)
   or not seen.

**Report file:** when you can run shell commands (Claude Code, Cursor) and the tools offer `save_as`, also build an
HTML report from saved files instead of retyping clips. Use one folder, e.g. `newscatcher-exports/<name>/` (`<dir>`):
`list_articles(query=<Q>, from=<start>, save_as="json", path="<dir>/clips.json")` (every clip up to 1,000, 5 credits
per 100); the tier-1 list with `save_as="json", path="<dir>/tier1.json"`; the daily count with `save_as="json",
path="<dir>/volume.json"`; the story search with `save_as="json", path="<dir>/stories.json"` (leave it out if most of
its stories are off topic). Write 5–10 lines of analysis to `<dir>/notes.md`, then run
`node <this skill's base directory>/scripts/render-report.mjs --title "<Company> <announcement> coverage" --subtitle "<window>" --articles "All coverage=<dir>/clips.json" --articles "Tier-1=<dir>/tier1.json" --counts "Daily coverage=<dir>/volume.json" --stories "Main stories=<dir>/stories.json" --notes <dir>/notes.md --out <dir>/report.html`.
If you can't write files, pass the notes on stdin: `--notes -` with a quoted heredoc (`<<'EOF'` … `EOF`). Give the
printed summary and the path in chat, alongside the report below.

## Deliver
```
<Company> <announcement> coverage · <start> → <end> (UTC)
| Articles (exact) | Original (no syndicated copies) | Outlets | Tier-1 outlets | Countries | Languages | Peak day |
Over time: daily counts, e.g. Nov 4: 3 · Nov 5: 12
Main story: <n> newsrooms, earliest article by <outlet> at <time> (as get_story lists it)
Key messages: <message>: picked up (1–3 example clips that show it, e.g. [Outlet](url)) | not seen in the headlines read
Top clips (tier-1 first, at most 8): date · outlet · headline · link
Method: query, fields searched, window, what the outlet/country counts are based on
```

## Quality bar
- Report plainly: only what the tool results say. No added causes, motives or labels ("main driver", "full licence",
  "positive tone"); if you give your own read, mark it as your read.
- A number appears only if a tool printed it or you counted it from rows you show; don't recompute a total a tool gave.
- Every count comes from a tool result; say when a count covers a sample (tallies read up to 1,000 newest matches).
- Count outlets and articles separately; syndication inflates articles.
- A message counts as picked up only when a headline or snippet shows it; say when it can't be verified from them.
- Off-topic clips found in reading are excluded and counted ("3 unrelated clips dropped").

## Before you send
Check each line; fix the answer where one fails.
- [ ] The headline numbers row is complete (write "n/a" where a tool gave nothing) and every number has its tool.
- [ ] Each key message has example clips that show it, or "not seen in the headlines read".
- [ ] Clip dates and times are copied from the results; outlets and links match.
- [ ] If two counts differ (e.g. a total and the sum of daily counts), report both and say they come from different calls.
- [ ] The method line names the query, fields, window and what the counts are based on.

## Done when
The report states exact coverage numbers, the clip list and the method, and each key message is marked picked up or
not seen.
