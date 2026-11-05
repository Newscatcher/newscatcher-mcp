---
name: multilingual-news
description: "Use when the user wants news from other countries or in other languages — what German, Japanese, Brazilian, Arabic or any local media say about a company, policy, event or person; regional perspectives; coverage that English media miss; comparing how countries cover the same story. Searches non-English news through translation and summarises it in the user's language with original sources."
---

# Multilingual news

What local media say, in their language, summarised for the user, with the original links.

Runs on the NewsCatcher MCP tools (`search_news`, `list_articles`, `count_articles`). If missing, see the
`newscatcher` skill.

## Run
1. `search_news(query=<topic in English or the local language>, languages=["de"], window="7d", group="story", limit=20)`.
   search_news matches non-English articles through their English translation and returns English headlines
   (`[EN: …]`) and summaries, so an English query works. Use `countries=["DE"]` for publishers in a country
   (whatever the language).
2. Exact local terms: `list_articles(query="<term in the local language>", languages=["de"], from="30 days ago")`, or
   an English query with `search_in=["title_translated"]`.
3. Compare countries: run step 1 per language, or `count_articles(queries=[same query], languages=[…])` per country.

## Deliver
- Per country/language: the main stories and angle, translated, with outlet names and original links.
- What differs from English-language coverage (emphasis, facts reported only locally, tone).

## Quality bar
- Keep the original headline next to the translation when quoting.
- Translation can blur nuance; flag strong claims for a native check.

## Done when
The user knows what local media are saying and how it differs, with sources in the original language.
