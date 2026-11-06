---
name: share-of-voice
description: "Use when the user wants share of voice, media mentions or coverage volume compared across brands, companies, products, people, candidates or topics — who gets more attention, how it changes week to week, which outlets and countries drive it. Produces exact mention counts over time from NewsCatcher and a share-of-voice table and chart data."
---

# Share of voice

Exact article counts per name over time, each name's share, the peaks and what drove them, and how it was counted.

Runs on the NewsCatcher MCP tools (`count_articles`, `list_articles`, `search_news`). If missing, see the
`newscatcher` skill.

## First
- Only when the request refers to the user's own brand without naming it ("we", "us", "our company"): ask for the
  name and stop, with no tool calls. When every name is given, go ahead.
- Period: as asked ("last month" = the previous calendar month; "last 3 months" = from 91 days ago to today); default
  the last 30 days. Interval: daily up to ~30 days, weekly up to ~6 months, monthly beyond. Say both in your first line.

## Write fair queries (this decides the result)
- The same style for every name: quote multi-word names (`"Goldman Sachs"`); add context only to ambiguous names
  (`"Zoho" AND (software OR CRM OR company)`, `"Mercury" AND (bank OR fintech)`); include common variants
  (`("Google DeepMind" OR DeepMind)`).
- Count headline mentions with `search_in=["title"]`: articles about the name, not passing mentions. Use the same
  fields and filters for every name.
- Check every name's query once (one call per name): `list_articles(query=<q>, from=<start>, search_in=["title"], page_size=5)`; if hits are
  off topic, tighten it.

## Run
1. `count_articles(queries=[<q1>, <q2>, …], from=<start>, to=<end>, interval=<day|week|month>, search_in=["title"])`.
   It allows 60 calls (buckets × names): 3 names × 13 weeks fits; split longer periods into two calls. It prints the
   totals, shares and each name's peak: use those figures, don't recompute them.
2. Peaks: for each name's peak bucket, `search_news(query="<name>", window=<a window covering that bucket>, group="story", limit=5)`
   (search_news covers the last 30 days), or for older peaks
   `list_articles(query=<q>, from=<bucket start>, to=<bucket end>, search_in=["title"], sort="source_rank", page_size=5)`.
   Do this for every name's peak (one search each), and explain a peak only with headlines from that bucket.
3. Optional: where each name is covered: `list_articles(query=<q>, from=<start>, tally="country")`; tier-1 share:
   step 1 again with `top_sources="top 100 US"`.

**Report file:** when the user wants a chart, a report or something to share, and you can run shell commands with
`save_as` available: add `save_as="json", path="<dir>/sov.json"` to step 1 and `save_as="json", path="<dir>/peaks.json"`
to a peak search, write the read and the peak causes to `<dir>/notes.md`, and run
`node <this skill's base directory>/scripts/render-report.mjs --title "Share of voice: <names>" --subtitle "<period>" --counts "Share of voice=<dir>/sov.json" --stories "What drove the peaks=<dir>/peaks.json" --notes <dir>/notes.md --out <dir>/report.html`
(notes on stdin with `--notes -` and a quoted heredoc if you can't write files). Give the printed summary and path.

## Deliver
```
Share of voice: <names> · <start> → now (UTC) · <n> <interval> buckets starting <start>, the last one partial · headline mentions
| Name | Articles | Share |   (from the tool's totals and shares)
One-line read: who leads, by how much, and how it moved (e.g. "Anthropic led with 50%, after an Oct 26 spike")
Table: bucket × name counts (n/a where a bucket could not be counted)
Peaks: <name> <bucket> (<count>): 1–2 headlines from that bucket with links
Chart data (CSV): the actual rows, starting with the header bucket,<name1>,<name2>,…
Method: the exact queries, fields searched, window, filters
```

## Quality bar
- Report plainly: only what the tool results say. No added causes, motives or labels ("main driver", "full licence",
  "positive tone"); if you give your own read, mark it as your read.
- A number appears only if a tool printed it or you counted it from rows you show; don't recompute a total a tool gave.
- Totals, shares and peaks come from the count output; a partial last bucket is labelled partial.
- Peak causes come from headlines in that bucket; with no clear headline, say "cause not clear from coverage".
- Say what a query can't separate (namesakes, a product vs the company) and how you limited it.

## Before you send
Check each line; fix the answer where one fails.
- [ ] The header gives the window, the number of buckets and that the last one is partial.
- [ ] Totals, shares and peaks are the ones count_articles printed.
- [ ] Every name's peak has 1–2 headlines from that bucket with links, or "cause not clear from coverage".
- [ ] The CSV chart data and the method line (exact queries) are there.

## Done when
The user sees who leads, how it moved, why it moved, and exactly how it was counted.
