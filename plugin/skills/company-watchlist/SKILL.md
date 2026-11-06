---
name: company-watchlist
description: "Use when the user wants to follow or monitor a set of companies — a portfolio, accounts, prospects, competitors, suppliers, a watchlist — and get their news now and as it happens: saves the companies as a list, runs company news research, and sets up a monitor that delivers only new stories on a schedule. Also for reviewing what a company monitor delivered, and for changing or pausing one."
---

# Company watchlist (company monitoring)

Follow a set of companies: a saved list, their recent news now, and a monitor that delivers only new stories on a
schedule. Also: read what a monitor delivered, and change it.

Runs on the NewsCatcher MCP tools (`save_company_list`, `get_company_list`, `edit_company_list`, `start_research`,
`get_research`, `get_monitor`, `get_monitor_updates`, `update_monitor`). If missing, see the `newscatcher` skill.

## Defaults (say them in one line at the top, e.g. "Defaults: every story, the last 14 days, daily at 09:00 UTC; tell me to change any")
- **Companies:** website domains. A name only: find the domain with a quick `search_news` and say which company you
  picked. No companies given: ask for them (a pasted list, or a CSV or XLSX file) and stop there.
- **Focus:** every story, unless the user names topics ("funding, M&A, leadership changes, layoffs"), which become `query`.
- **First look back:** what the user asked, else 14 days.
- **Schedule:** what the user asked; else daily at 09:00 in the user's timezone if known, else UTC.
- **Cost:** about 500 credits per company for a company run; a company monitor is 3,000 credits per company per month at list
  price. `dry_run=true` on the same start_research call shows the exact cost for free; use it for long lists or when
  the user asks about cost.

## New watchlist
1. `save_company_list(name=<name>, companies=[<domains>])` (or `csv_path=<file>` for a long list). The result shows
   each company's identification status ("resolving" is fine: runs wait for it). Fix one marked not_found, or
   identified as the wrong business, with
   `edit_company_list(list_id=<id>, correct={"domain": "<domain in list>", "new_domain": "<right domain>"})`, or drop it
   with `edit_company_list(list_id=<id>, remove=["<domain>"])`.
2. Baseline and monitor in one call:
   `start_research(company_list_id=<id>, query=<focus, or leave out>, lookback_days=<days>, keep_updated={"every": "week", "weekday": 0, "at": "09:00", "tz": "<IANA tz>"})`.
   Daily: `keep_updated={"every": "day", "at": "08:00", "tz": "America/New_York"}`. A one-off look with no ongoing
   watch: leave out `keep_updated`. The monitor is created when this run succeeds and from then on delivers only
   stories newer than the baseline (or stories that grew).
3. `get_research(run_id, wait_seconds=300, sort="importance")` until it finishes (about 2–4 minutes per 6 companies). If you must stop
   first, give the run id and ask the user to say "refresh". The finished run shows the monitor id under "Keep updated";
   if it still says pending, call `get_monitor()` once: report the monitor id and next run, or say it is being created
   and will appear there within minutes.

## Existing watchlist
- Find it: `get_monitor()` lists monitors; `get_company_list()` lists saved lists.
- What's new: `get_monitor_updates(monitor_id=<id>)` is the latest delivery, each story marked new or update.
  The full recent feed: `get_monitor_updates(monitor_id=<id>, feed=true, days=7)`.
- Change it: `update_monitor(monitor_id=<id>, action="edit", query=<new focus>)` or `schedule={…}`;
  `action="pause"`, `"resume"` or `"run_now"`. Add companies with `save_company_list(list_id=<id>, companies=[…])`:
  monitors that follow the list pick them up on their next run.

## Deliver
**Setup:** one block with the list (id, companies, and which are identified, still resolving, or not found: say
"still resolving" rather than claiming an identity the tools haven't confirmed) and the monitor (id, schedule with
timezone, focus, when the first delivery comes, where to read it, and how to change or pause it).

**Baseline or delivery:** first the total ("<n> stories across <m> companies", from the coverage and "Counts over all
N rows" lines), then per company, most important stories first, at most 3 per company (date · story type · headline ·
link), each with one line starting "Our read:" on why it matters for the user's purpose (portfolio, sales,
competition, supply); that line is your interpretation, so keep it short and tied to the story. Then "No
news in this window: <companies>". At most 25 stories inline. Copy links exactly; never shorten one.

**Delivery channels:** monitors deliver into NewsCatcher (read here with `get_monitor_updates`, or through the Agent
API). For email or Slack, a small script polls the monitor and posts the new stories (see the `news-alerts-integration`
skill). Never say updates will arrive by email or Slack unless that has been set up.

## Quality bar
- Report plainly: only what the tool results say. No added causes, motives or labels ("main driver", "full licence",
  "positive tone"); if you give your own read, mark it as your read.
- A number appears only if a tool printed it or you counted it from rows you show; don't recompute a total a tool gave.
- Every story, date and link comes from the run or the monitor output; importance and story type as the run gives them.
- Say which companies had no coverage: silence is information.
- Don't re-report stories already delivered unless they grew (marked update).
- One domain per company; identities checked and fixed before the first run.

## Before you send
Check each line; fix the answer where one fails.
- [ ] The defaults line is the first line (focus, look-back, schedule with timezone) with how to change them.
- [ ] Every story has a date, a story type, a headline and a link copied exactly, plus one "why it matters" line.
- [ ] Companies with no news are named.
- [ ] Where to read updates (get_monitor_updates in NewsCatcher) is stated; no promise of email or Slack.

## Done when
The list is saved and checked, the baseline is delivered, and the monitor exists with its schedule, focus and next
delivery stated (or, for a review, the new stories are delivered and the monitor's state is clear).
