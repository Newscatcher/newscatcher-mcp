---
name: news-briefing
description: "Use when the user wants a news briefing, digest, roundup, summary of the news, \"what's new with X\", a morning or weekly brief on a topic, industry, company, country or person — recent developments grouped by theme, each claim linked to its source. Produces a cited briefing from NewsCatcher news search, and can be scheduled."
---

# News briefing

A short, cited briefing: what changed, why it matters, what to watch. Built from NewsCatcher's ranked, story-grouped
news search, so one event appears once even when 40 outlets covered it.

Runs on the NewsCatcher MCP tools (`search_news`, `get_story`, `count_articles`). If they are missing, see the
`newscatcher` skill for setup.

## Ask first (only what's missing)
- Topic and scope (an industry, a company, a country, a person).
- Window: default the last 7 days; "today" = `1d`, "this morning" = `12h`.
- Audience and length: default 5–8 bullets plus "what to watch".
- Languages or regions to include or exclude (default: every language).

## Run
1. `search_news(query=<topic in plain words>, window=<window>, group="story", limit=20, effort="medium")`.
   For a broad topic run 2–3 searches on its sub-angles (e.g. for "EV market": pricing, sales, policy, batteries).
2. Keep stories that are about the topic and recent; drop duplicates (same story id) and off-topic namesakes.
3. For the 2–3 biggest stories (most newsrooms), `get_story(story_id, limit=10)` for the earliest report and the most
   authoritative outlets.
4. Optional, when "is this getting bigger" matters: `count_articles(queries=[<boolean query>], from=<start>, interval="day")`.

## Deliver
```
**<Topic> — <window>** (sources: N stories, M newsrooms)
**Top line:** one sentence on what changed.
- **<Theme>:** what happened, with numbers and dates. [Outlet](url)
- …
**What to watch:** 2–3 upcoming dates, decisions or open questions.
```
Lead with the most important change, not the most recent. Use English, translate foreign-language stories and keep
their original outlet link.

## Quality bar
- Every claim has a link from the results; no facts beyond what the articles say.
- Name coverage strength: "covered by 105 newsrooms" vs "one report so far".
- Separate reporting from opinion and rumour ("reported", "according to", "unconfirmed").
- No investment, legal or medical advice.

## Keep it running
A recurring briefing is a schedule plus this skill: Claude Code `/schedule` or `/loop`, or a cron job running
`newscatcher-mcp call search_news '{…}'`. For a company list, a monitor is cheaper: see `company-watchlist`.

## Done when
The briefing answers "what changed in <window>" with linked sources, and the user knows what to watch next.
