---
name: news-trend-analysis
description: "Use when the user asks whether a topic is trending, rising or fading in the news, wants to see news volume over time, detect spikes, compare periods (this month vs last), or understand what drove a surge in coverage — for any topic, keyword, company, product or event. Produces exact daily or weekly article counts and explains each spike with the stories behind it."
---

# News trend analysis

Is coverage rising? When did it spike, and why?

Runs on the NewsCatcher MCP tools (`count_articles`, `list_articles`, `search_news`, `get_story`). If missing, see the
`newscatcher` skill.

## Run
1. Turn the topic into a precise boolean query (see the `share-of-voice` skill on query precision). Check it with
   `list_articles(query, page_size=5)`.
2. `count_articles(queries=[query], from=<start>, interval="day")` for up to ~30 days; `week` or `month` for longer
   (up to 12 months).
3. Find spikes: buckets above ~2× the median. For each, `search_news(query=<topic>, window=…)` or
   `list_articles(query, from=<day>, to=<next day>, sort="source_rank", page_size=10)` to name the driver; `get_story`
   for its size.
4. Compare periods with two buckets (e.g. month over month) or two queries (topic vs topic).
5. Optional breakdowns: same counts with `languages=[…]` or `countries=[…]` to see where it is rising.

## Deliver
- The timeline (table + CSV-ready data), trend direction with the numbers ("+64% week over week"), peak dates and
  their drivers with links.
- What it means and what to watch.

## Quality bar
- Weekend dips are normal; compare like with like (weekday vs weekday, week vs week).
- Volume is not sentiment: describe the stories, don't infer tone from counts.

## Done when
The user knows the direction, the peaks and the stories behind them, with exact numbers.
