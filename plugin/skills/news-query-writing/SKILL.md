---
name: news-query-writing
description: "Use when a news search returns too much, too little or the wrong thing, or before an important count, screen or export — writing precise NewsCatcher queries: boolean syntax for list_articles and count_articles (AND, OR, NOT, phrases, NEAR, wildcards, search_in), plain-language queries for search_news, handling ambiguous company names, synonyms, multiple languages and noise. Tests the query on real results before using it."
---

# Writing news queries

Get the right articles: precise enough to exclude namesakes, broad enough to catch synonyms.

## search_news (relevance)
- Write what you want in plain words; the ranking handles synonyms: "layoffs at European banks this month".
- Use `NOT` (upper case) to drop a dominant wrong meaning: `Apple NOT iPhone` for corporate news.
- Narrow with filters, not words: `languages`, `countries`, `sources`, `min_newsrooms`, `window`.

## list_articles / count_articles (boolean, exact)
- Bare words are ANDed: `Tesla recall` = Tesla AND recall.
- Phrases in quotes: `"Bank of America"`; synonyms in OR groups: `(layoff OR layoffs OR "job cuts" OR redundancies)`.
- Namesakes: add context — `"Mercury" AND (bank OR fintech OR banking)`, `"Shell" AND (oil OR energy OR "Royal Dutch")`.
- Proximity: `NEAR("Nvidia", "export controls", 10)`.
- Wildcards: `regulat*`. Must/must-not: `+Tesla -Musk`.
- Where: `search_in=["title"]` for articles about the subject (precise); `title_body` (default) for any mention;
  `title_body_translated` to match other languages through their English translation.
- Volume sanity: `count_only=true` first. Thousands for a niche topic usually means the query is too loose.

## start_research (the research agent)
- Describe the events, not the coverage: "Series A rounds raised by European fintech startups since October 1,
  2026, with amount and lead investor", not "news articles about fintech funding".
- One sentence: event + who/where + window + the fields you want; 2–4 specifics, not a long list of conditions.
- `start_research(query=…, dry_run=true)` checks the query (window, wording) and shows time and cost, free.

## Test before trusting
1. `list_articles(query, page_size=10, sort="relevance")` — read the 10 titles: are they on topic?
2. `list_articles(query, page_size=10, sort="newest")` — are recent ones on topic too?
3. Tighten (title only, context terms, NOT) or loosen (synonyms, translated fields) and repeat.
4. Record the final query with the result, so the count can be reproduced.

## Done when
A sample of results is clearly on topic and the query is written down next to the numbers it produced.
