---
name: earnings-season
description: "Use when the user wants earnings coverage for a set of companies or tickers: results versus expectations, guidance changes, management comments, analyst and market reaction, an earnings calendar recap or a sector earnings round-up. Reports what the news says with sources; never gives investment advice."
---

# Earnings season

What each company reported, how it compared with expectations, what it said about guidance, and how the news read
it, with links. Reporting only, no buy or sell views.

Runs on the NewsCatcher MCP tools (`search_news`, `get_story`, `start_research`, `get_research`, `count_articles`). If
missing, see the `newscatcher` skill.

## Defaults (say them in your first line)
- "This week" = since Monday 00:00 UTC; otherwise results published in the last 14 days.
- "Big tech" = Apple, Microsoft, Alphabet, Amazon, Meta, Nvidia, Tesla, plus any other large tech company whose
  results the search finds in the window. Name the companies you covered.

## Run
- **Named companies (up to ~10):** per company
  `search_news(query="<Company> quarterly results revenue earnings guidance", window=<window>, group="story", limit=8)`;
  then `search_news(query="<Company> earnings analysts expectations estimates shares", window=<window>, limit=6)` for
  consensus and reaction when the first search lacks them. Add `languages` for non-English filers.
- **A sector or "this week's earnings":** find who reported with
  `search_news(query="<sector> quarterly results beat miss estimates guidance", window=<window>, group="story", effort="high", limit=30)`,
  then one per-company search for the 5–6 biggest reporters. Keep to about 10 searches.
  For "this week", use `window` covering Monday to now (e.g. "4d" on a Thursday). The table holds only companies
  whose results articles are dated Monday or later; every such company the searches found gets a row (up to 10),
  and anything earlier goes in one line under the table ("reported last week: …"), not in the table. Every company
  that reported in the window is a table row, never a prose mention ("not reported" in cells the articles don't
  cover). For "big tech", add a line naming each default company with no results in the window ("No results this
  week: Microsoft, Alphabet, …"). A theme bullet stays only if it links an article that states it.
- **A cross-market question (e.g. "who cut guidance in Europe"):**
  `start_research(query="Companies headquartered in <region> that <cut/raised> their full-year guidance between <start> and <end>, with company, country, sector, date, previous and new guidance, reason and source", mode="fast", max_rows=50)`,
  then `get_research(run_id, wait_seconds=300)` until it finishes; if you must stop first, give the run id and ask the
  user to say "refresh". One fast run is about 1,000 credits; `dry_run=true` shows the cost.
- **How big the reaction story is:** `get_story(story_id)` for the main story's newsroom count.

## Deliver
1. First line: window, companies covered, and any that had not reported in the window.
2. Table, one row per company:

   | Company | Reported (UTC date) | Results as reported | vs expectations | Guidance | Reaction | Source |

   "vs expectations" says beat, miss or in line only when an article says so, with the consensus figure if given;
   otherwise "not reported". Guidance: raised, cut, reaffirmed or initiated only when an article uses that word
   (else quote the outlook as given, e.g. "Q4 revenue of 9.6 billion, plus or minus 300 million"); metric names exactly as the article gives them.
3. 3–5 bullets on themes across companies (demand, margins, AI spending, China, costs), each with a link.

For a list from a research run (e.g. who cut guidance), use the run's own columns instead: | Company | Country |
Date | Guidance change (old → new) | Reason | Source |, at most 10 rows, and say how many more the run found (its
row count minus the rows shown).

## Quality bar
- Report plainly: only what the tool results say. No added causes, motives or labels ("main driver", "full licence",
  "positive tone"); if you give your own read, mark it as your read.
- A number appears only if a tool printed it or you counted it from rows you show; don't recompute a total a tool gave.
- Numbers exactly as reported, with currency, unit and period (Q3 FY2026); company figures separate from analyst
  estimates.
- Reported date = the date the articles give for the results (else the earliest article's date, saying so); add
  "after the close" or "pre-market" only when an article says it.
- A row for every company in scope: "no results reported in the window" is a valid row.
- Every number and link comes from the results; don't fill a gap from memory.
- No price predictions or recommendations; if asked, say this reports the news only.

## Before you send
Check each line; fix the answer where one fails.
- [ ] The first line gives the window and the companies covered.
- [ ] Each row's date and figures come from the article that row links to.
- [ ] Beat, miss, raised and cut appear only where an article uses those words.
- [ ] Each theme bullet links to an article that states it.

## Done when
Every company in scope has a sourced row (or "not reported yet"), and the themes are tied to links.
