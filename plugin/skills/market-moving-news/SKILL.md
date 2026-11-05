---
name: market-moving-news
description: "Use when the user wants news that moves or explains markets and stocks — why a stock moved, earnings coverage, guidance, analyst actions, macro events, central-bank decisions, sector news for a watchlist of tickers or companies, pre-market catch-up. Finds and summarises the relevant stories with NewsCatcher, with timestamps, without giving investment advice."
---

# Market-moving news

Which stories moved or explain a market, a sector or a stock, in time order, with the reported numbers and sources.

Runs on the NewsCatcher MCP tools (`search_news`, `get_story`, `count_articles`, `start_research`). If missing, see
the `newscatcher` skill.

## Defaults (say them in your first line)
- "Today" = the last 24 hours; "this week" = since Monday 00:00 UTC; otherwise the last 2 days.
- Markets: what the user named; for "the market" use the US and Europe, plus Asia when the window includes its session.
- NewsCatcher reports the news, not prices: give price moves only as the articles report them, with the article time.

## Run
- **The market today:** `search_news(query="stock market stocks indexes rally selloff why", window="1d", group="story", effort="high", limit=20)`,
  then one search per driver you see (rates, earnings, oil, tariffs, a big stock):
  `search_news(query="<driver> markets stocks", window="1d", group="story", limit=10)`.
- **Why did <company> move:** `search_news(query="<Company> shares stock", window=<window>, sort="newest", limit=15)`, then
  `search_news(query="<Company> <driver: earnings, guidance, downgrade, deal, regulator, product>", window=<window>, group="story", limit=10)`.
  Line the stories up by time against the move the articles describe.
- **A sector or region:** `search_news(query="<sector> <region> shares stocks", window="1d", group="story", effort="high", limit=20)`,
  e.g. "European banks shares stocks"; add `languages` or `countries` for local coverage.
- **How big a story is:** `get_story(story_id)` for its newsroom count and first report.
- **Attention spike (optional):** `count_articles(queries=["\"<Company>\""], from="10d", interval="day", search_in=["title"])`.
- **A watchlist of many companies:** `start_research(companies=[<domains>], lookback_days=3, query="earnings, guidance, analyst actions, deals, regulatory, management changes")`,
  then `get_research(run_id, wait_seconds=300)` until it finishes; if you must stop first, give the run id and ask the
  user to say "refresh". About 500 credits per company; check with `dry_run=true` first for more than 20.

## Deliver
1. First line: "Window: <from> → <to> UTC · Markets: <markets covered>".
2. The drivers, most important first; for each:
   **<Driver>**: what happened, the numbers as reported (index or share moves, results versus expectations, rate
   decisions), when (UTC), and 1–2 sources written as `[Outlet](url) · <N> newsrooms` (N from the result's story
   line; write "1 newsroom" when the result has no story line).
3. For a single stock: a section titled "Timeline" (time UTC · event · source, oldest first), then the reported move.
4. What isn't covered: markets or hours the results don't reach (e.g. "no Asian session coverage yet").

## Quality bar
- Report plainly: only what the tool results say. No added causes, motives or labels ("main driver", "full licence",
  "positive tone"); if you give your own read, mark it as your read.
- A number appears only if a tool printed it or you counted it from rows you show; don't recompute a total a tool gave.
- Every move, number, time and link comes from the search results; quote numbers exactly, with currency and index,
  and name an index only when the article names it ("European shares rose 0.5%" stays as written).
- Give each cited story's newsroom count as the result shows it ("story … (N newsrooms)"); call a story the biggest
  only after comparing those counts.
- Each driver gets at least one link; leave out claims you can't link.
- Separate what happened (results, decisions, deals) from commentary and forecasts; label analyst views as such.
- Don't name an outlet as the origin of a story, or a story as the main one, unless the results show it (earliest
  time, most newsrooms).
- No predictions, no buy or sell views, no investment advice; if asked, say this reports the news only.

## Before you send
Check each line; fix the answer where one fails.
- [ ] The first line gives the window and the markets covered.
- [ ] Every bullet has a link, and next to each link the newsroom count from that same result.
- [ ] Each number is quoted as the article gives it; no causes or rankings the articles don't state.
- [ ] Gaps (markets or hours not covered) are named.

## Done when
Each move or event in scope has its explaining stories with times and sources, and the coverage gaps are named.
