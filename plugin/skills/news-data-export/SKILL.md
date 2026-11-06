---
name: news-data-export
description: "Use when the user wants to pull an exact set of news articles into a file or database for analysis, research, dashboards or ML datasets: every article matching a boolean query over a period, as CSV, Parquet or JSON, with paging, the per-query cap, window splitting and deduplication handled. Uses list_articles or the NewsCatcher /articles REST endpoint."
---

# News data export

Every article that matches a query over a period, in a file, with exact totals.

Runs on `list_articles` / `count_articles` for small pulls, or the REST endpoint for big ones. Key from
`NEWSCATCHER_API_KEY`; host `https://api.newscatcherapi.com/news-api`; header `x-api-key`.

## Ask first (only what you can't infer)
- The query (boolean), period (up to 12 months back), languages/countries, fields needed, and the output format.

## Plan the pull
1. Size it: `list_articles(query=…, from=…, to=…, count_only=true)` (5 credits). Each page is one call (5 credits, up to
   100 articles); only the first 1,000 matches of one query window can be paged.
2. Over 1,000: split the period. `count_articles(queries=[…], from=…, to=…, interval="day")` shows daily volume; make
   windows that each hold under 1,000 (days, or hours on busy days).
3. Estimate credits = pages × 5 and confirm with the user when it is more than a few hundred calls.

## Pulls up to 1,000 per window (no code)
`list_articles(query=…, from=…, to=…, save_as="csv")` (or `save_as="json"`, optional `path`) pages through every match
with the window end pinned and writes the file locally; only a summary comes back, so the rows never fill the
conversation. Over 1,000: one `save_as` call per window from the split above, then merge and drop duplicate ids.

## Big pulls (code)
```python
import os, time, requests, pandas as pd
URL = "https://api.newscatcherapi.com/news-api/articles"
H = {"x-api-key": os.environ["NEWSCATCHER_API_KEY"], "content-type": "application/json"}

def pull(q, start, end, **filters):
    rows, page = [], 1
    while True:
        body = {"q": q, "from_date": start, "to_date": end, "page": page, "page_size": 100,
                "sort_by": "-published_at", "exclude_duplicates": True, **filters}
        r = requests.post(URL, headers=H, json=body, timeout=60)
        if r.status_code == 429:
            time.sleep(float(r.headers.get("retry-after", 2))); continue
        r.raise_for_status()
        d = r.json()
        rows += [{"id": a["id"], "published_at": a["published_at"], "title": a["title"], "title_en": a.get("title_en"),
                  "source": (a.get("source") or {}).get("domain"), "language": a.get("language"),
                  "country": a.get("country"), "url": a["url"], "snippet": a.get("snippet")} for a in d["results"]]
        if page >= d.get("total_pages", 1) or page * 100 >= 1000:
            if d["total_hits"] > 1000: print(f"window {start}..{end} has {d['total_hits']} > 1000: split it")
            return rows
        page += 1; time.sleep(1.05)  # stay under ~1 request/second

days = pd.date_range("2026-08-01", "2026-11-01", freq="D")
all_rows = []
for a, b in zip(days[:-1], days[1:]):
    all_rows += pull('"electric vehicle" AND (battery OR charging)', a.isoformat() + "Z", b.isoformat() + "Z", languages=["en"])
df = pd.DataFrame(all_rows).drop_duplicates("id")
df.to_parquet("articles.parquet"); df.to_csv("articles.csv", index=False)
```

## Quality bar
- Report the exact `total_hits` per window next to what was pulled; flag any window above 1,000.
- Deduplicate by article id (windows can touch at the edges).
- Store the query, filters and pull time with the data so it can be reproduced.
- Results carry headlines, snippets, metadata and links; link out for anything more.

## Done when
The file exists, its row count matches the summed totals (minus duplicates), and the user knows the credits used.
