---
name: news-api-bakeoff
description: "Use when the user wants to compare NewsCatcher with other news or web search APIs (Exa, Tavily, Perplexity, NewsAPI.org, Google News, Perigon, Bing…) on their own queries — relevance, freshness, coverage, languages, duplicates, cost per useful result — with a fair, repeatable method. Designs and runs the bake-off and reports results honestly."
---

# News API bake-off

A fair comparison on the user's own queries, judged the same way for every provider.

## Design (agree with the user first)
- 20–50 real queries from their use case (not cherry-picked), each with a time window.
- Metric per query: precision@10 (relevant, on-topic, real news, in window), distinct stories in the top 10
  (duplicates count once), freshness (median age), coverage (exact total where available), languages, cost per
  query and per relevant result.
- Same window and result count for every provider; blind judging (shuffle, hide provider names).

## Run
1. NewsCatcher: `search_news(query, window, limit=10, effort="medium")` (also `high` if quality matters most);
   exact coverage with `list_articles(query, count_only=true)`.
2. Other providers through their own tools or APIs with equivalent settings; keep the raw results.
3. Judge each result (relevant? real news? in window?) — the same rubric, the same judge, provider hidden.
4. Aggregate per provider; report means with spread, not single queries.

## Report
Table per provider: P@10, distinct stories, median age, cost per relevant result; where each wins and loses, with
example queries. Note limitations (sample size, judge, windows).

## Quality bar
- Don't publish or redistribute another provider's raw results; many terms of service forbid it. Share aggregates.
- Report where NewsCatcher loses too.

## Done when
The user has a repeatable method, the numbers, and examples behind them.
