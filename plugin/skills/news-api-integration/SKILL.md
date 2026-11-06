---
name: news-api-integration
description: "Use when the user is writing code that calls the NewsCatcher News API — adding news search to an app, backend, data pipeline or agent; choosing between /search, /articles and /stories; handling auth, effort, pagination, rate limits, credits and errors; or generating a typed client in Python, TypeScript or another language. Gives correct endpoints, parameters and production patterns."
---

# Build with the NewsCatcher News API

Base URL `https://api.newscatcherapi.com/news-api`, header `x-api-key: <key>`. OpenAPI spec:
`https://api.newscatcherapi.com/news-api/openapi.json` — generate types from it rather than hand-writing them.

## Pick the endpoint
| Need | Endpoint | Notes |
|---|---|---|
| Best articles for a question or keywords, last 30 days | `GET/POST /search` | `effort` low/medium/high = 1/5/10 credits; `limit` ≤ plan max (50 on free) |
| Every article matching a boolean query, last 12 months | `GET/POST /articles` | 5 credits per page; `page_size` ≤ 100; first 1,000 per query; exact `total_hits` |
| All articles of one story | `GET /stories/{story_id}` | 1 credit; `story.id` comes from `/search` |
| Plan, limits, balance | `GET /subscription` | free |

## Patterns
- **Keep keys server-side.** Never ship the key to a browser or mobile app; proxy through your backend.
- **POST with a JSON body** for anything non-trivial; list params can be arrays.
- **Paging /articles:** read `window.to` from page 1 and send it as `to_date` on every next page, so all pages cover
  the same set. Stop at `page * page_size >= min(total_hits, 1000)`; narrow the window for more.
- **Story-aware UIs:** show one card per `story.id` (`collapse=story`) with `story.newsrooms` as "N outlets".
- **Rate limits:** 429 carries `Retry-After`; back off and retry. `/articles` is 1 request/s on the free plan.
- **Errors:** body `{message, status_code, status}`. Retry 429/500/503 (and 408 on /articles with a narrower window);
  don't retry 401/402/403/422. Log the `Correlation-ID` response header.
- **Costs:** a 200 is charged even with 0 results; failed requests are free. Cache identical requests briefly.
- **Time:** `search_window` (`2h`, `1d`, `7d`) on /search; `from_date`/`to_date` (ISO or "7 days ago") on /articles.

## Minimal examples
```python
import os, requests
r = requests.post("https://api.newscatcherapi.com/news-api/search",
                  headers={"x-api-key": os.environ["NEWSCATCHER_API_KEY"]},
                  json={"q": "Nvidia guidance", "effort": "medium", "limit": 10, "search_window": "2d"}, timeout=60)
r.raise_for_status()
for a in r.json()["results"]:
    print(a["published_at"], a["source"]["name"], a["title"], a["url"], a["story"]["newsrooms"])
```
```ts
const res = await fetch("https://api.newscatcherapi.com/news-api/articles", {
  method: "POST",
  headers: { "x-api-key": process.env.NEWSCATCHER_API_KEY!, "Content-Type": "application/json" },
  body: JSON.stringify({ q: '"OpenAI" AND (lawsuit OR sued)', from_date: "30 days ago", page_size: 100 }),
});
const page = await res.json(); // { total_hits, total_pages, window: { from, to }, results: [...] }
```

## Done when
The integration uses the right endpoint, pages correctly, handles 429/5xx with retries, keeps the key server-side,
and the user has run one real request successfully.
