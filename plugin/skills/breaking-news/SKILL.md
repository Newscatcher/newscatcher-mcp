---
name: breaking-news
description: "Use when the user asks what is happening right now or in the last few hours — breaking news, live developments, \"is anything being reported about X\", a sudden event (earthquake, outage, attack, market move, election result), or wants the very latest on a developing story. Searches the last minutes to hours and reports what is confirmed, by whom, and when."
---

# Breaking news

What is being reported right now, from how many newsrooms, and how fast it is spreading.

Runs on the NewsCatcher MCP tools (`search_news`, `get_story`, `list_articles`). If missing, see the `newscatcher` skill.

## Run
1. `search_news(query=<event in plain words>, window="3h", sort="newest", limit=15, effort="low")` — fast.
   Nothing found: widen to `12h`, then `1d`, and say so.
2. Re-rank the hits with `search_news(…same query…, window=<same>, effort="medium", group="story")` when there are
   many unrelated results.
3. For the main story, `get_story(story_id)`: first report time, newsroom count, latest article.
4. Need the exact pace? `list_articles(query=<boolean>, from="6 hours ago", count_only=true)` now and again later.

## Deliver
- One line: what is being reported, first seen at <time UTC>, by <N> newsrooms.
- 3–6 bullets of the confirmed facts, each with outlet + time + link, newest first.
- What is not confirmed yet (casualty counts, causes, statements) — label as unconfirmed.
- When to check again (developing stories move fast; offer a re-check in 30–60 minutes).

## Quality bar
- Times in UTC (or the user's zone, converted) and explicit: "as of 14:05 UTC".
- Prefer wire services and major outlets for facts; flag single-source claims.
- Never fill gaps with speculation.

## Done when
The user knows what happened, how confirmed it is, and when the picture was last updated.
