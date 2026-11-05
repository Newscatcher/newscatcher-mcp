---
name: story-deep-dive
description: "Use when the user wants the full picture of one news story or event — a timeline of how it unfolded, who broke it, how coverage spread across outlets and countries, the key facts and how they changed, and what different outlets emphasise. Builds an event timeline from story coverage and exact article counts."
---

# Story deep dive

One event, end to end: first report, how it spread, how the facts evolved, and where it stands.

Runs on the NewsCatcher MCP tools (`search_news`, `get_story`, `list_articles`, `count_articles`). If missing, see the
`newscatcher` skill.

## Run
1. Find the story: `search_news(query=<event>, window="30d", group="story", effort="high", limit=10)`; pick the story
   with the most newsrooms that matches the event (confirm with the user if two are plausible).
2. `get_story(story_id, limit=100)`: earliest and latest articles, newsroom count, top outlets.
3. Related stories (follow-ups, reactions, analysis) often sit in other story ids: search the follow-up angles
   (`<event> investigation`, `<event> reaction`, `<event> aftermath`) with `group="story"`.
4. Attention curve: `count_articles(queries=[<boolean query for the event>], from=<first day>, interval="day")`.
5. Older than 30 days: `list_articles(query=…, from=…, to=…, sort="oldest")` to find the first reports.

## Deliver
- **Summary** (3 sentences) and **status now**.
- **Timeline**: dated entries (UTC), each with what changed and a link; mark the first report.
- **Coverage**: newsrooms, countries/languages, the attention curve (peak day and size).
- **How the facts changed**: early claims later corrected, numbers revised.
- **Open questions**.

## Quality bar
- Dates and times from the articles, not guessed.
- Distinguish the event date from the publication date.
- Each timeline entry has its source.

## Done when
Someone who missed the story could understand it from the timeline alone.
