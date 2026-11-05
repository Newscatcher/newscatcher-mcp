---
name: migrate-from-newsapi-org
description: "Use when the user wants to switch code from NewsAPI.org (newsapi.org /v2/everything or /v2/top-headlines), GNews, NewsData.io, World News API, Mediastack or a similar news API to NewsCatcher — maps endpoints, parameters and response fields, rewrites the calls, and checks results side by side."
---

# Migrate to NewsCatcher from another news API

Map each call, rewrite it, and compare results on real queries before switching.

## Endpoint map (NewsAPI.org → NewsCatcher, base `https://api.newscatcherapi.com/news-api`, header `x-api-key`)
| NewsAPI.org | NewsCatcher | Notes |
|---|---|---|
| `/v2/everything?q=` | `/articles?q=` | boolean query; exact `total_hits`; up to 12 months back; 1,000 articles per query |
| `/v2/everything` sorted by relevancy | `/search?q=` | ranked, story-grouped, plain-language queries, last 30 days |
| `/v2/top-headlines` | `/search` with `sort_by=published_at` and `min_newsrooms` (or `countries`) | "top" = stories many newsrooms cover |
| `apiKey` param / `X-Api-Key` | `x-api-key` header | |

## Parameter map
| NewsAPI.org | NewsCatcher /articles |
|---|---|
| `q` | `q` (AND/OR/NOT, quotes, `NEAR()`, wildcards) |
| `searchIn=title,description,content` | `search_in=title`, `title_body` (default), `summary` |
| `from`, `to` | `from_date`, `to_date` |
| `language` | `languages` (list) |
| `domains`, `excludeDomains` | `sources`, `not_sources` |
| `sortBy=publishedAt|relevancy|popularity` | `sort_by=published_at|relevancy|rank` |
| `pageSize`, `page` | `page_size` (≤100), `page` |

Response: `articles[]` → `results[]`; `source.name` stays; `publishedAt` → `published_at`; `urlToImage` → `image_url`;
`description` → `snippet` (short); `totalResults` → `total_hits` (exact). Also new: `language`, `country`, `rank`,
`story.id`/`story.newsrooms` on /search.

## Steps
1. Find every call site (grep for `newsapi.org`, the SDK import, `apiKey`).
2. Add a small client (see `news-api-integration`) and swap call sites behind one function.
3. Side by side on 10 real queries: count overlap, freshness and coverage (`total_hits`); expect more results and
   more languages.
4. Update pagination to the `window.to` pattern; update rate-limit and error handling (429 `Retry-After`).
5. Remove the old key from config.

## Done when
All call sites use NewsCatcher, tests pass, and the side-by-side check shows equal or better results.
