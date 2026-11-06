---
name: sales-trigger-events
description: "Use when the user wants sales triggers, buying signals or reasons to reach out — companies that just raised money, hired an executive, expanded, launched, opened an office, got acquired, announced layoffs or a new initiative — either across a market (\"Series A fintech startups in Europe this month\") or for a list of accounts. Produces a ranked list of companies with the trigger, date, why it matters and the source."
---

# Sales trigger events

Companies with a fresh, public reason to talk to you: the trigger, the date, why it matters for your offer, and the
source.

Runs on the NewsCatcher MCP tools (`start_research`, `get_research`, `export_research`, `save_company_list`). If
missing, see the `newscatcher` skill.

## First
- **Account list** given (domains or names): go straight to Run.
- **Market-wide:** you need the ideal customer (industry, geography; size or stage if it matters) and the triggers.
  If the industry or the geography is missing, ask one question for both and stop; don't run a paid search on a
  guessed territory.
- Defaults: the last 30 days (state the exact dates); triggers = what the user named, else funding, a new executive in
  the buyer's role, expansion, acquisitions, layoffs. Say them in your first line.

## Run
**Account list:**
1. `start_research(companies=[<domains>], query="<the triggers, e.g. funding, executive hires, expansion, layoffs, acquisitions>", lookback_days=30)`
   (over 20 accounts: `save_company_list` first and use `company_list_id`; show the cost with `dry_run=true`).
2. `get_research(run_id, wait_seconds=300)` until it finishes; if you must stop first, give the run id and ask the user
   to say "refresh". The coverage line lists accounts with no news.

**Market-wide:**
1. `start_research(query="<Trigger 1> or <trigger 2> at <industry> companies in <geography> between <start> and <end>, with company, website, trigger type, detail (amount, role and person, location), date and source", mode="fast", max_rows=50)`.
   One run can cover two related triggers (e.g. funding or a new CFO); for more, run one per trigger.
2. `get_research(run_id, wait_seconds=300)` until it finishes. More than 25 rows, or the user wants a file:
   `export_research(run_id, file_format="csv")` and give the path.

## Deliver
1. First line: scope, triggers and window; "<n> events found" (the run's row count), "<m> in the table" (the rows
   you show).
2. Ranked table, at most 10 rows (the most important or newest; say how many more there are and where: the run or the file):

   | # | Company | Trigger | Date | Detail | Why now (our read) | Source |

   Rank: fit first, then freshness, then strength (two triggers beat one). **Why now** is one line linking the
   trigger to the user's offer, e.g. "New CFO: finance tooling often gets reviewed"; no offer given, state what the
   trigger is (e.g. "raised a Series B led by Accel") without guessing needs. When the offer is given, every "why now"
   names how the trigger relates to it. When a row doesn't state the sector or location, keep it and add
   "(scope unclear)" to its Detail cell.
3. Below the table: "<a> in the table · <c> left out (other triggers, industry, region) · <d> duplicates merged",
   adding up to the run's rows.

## Quality bar
- Report plainly: only what the tool results say. No added causes, motives or labels ("main driver", "full licence",
  "positive tone"); if you give your own read, mark it as your read.
- A number appears only if a tool printed it or you counted it from rows you show; don't recompute a total a tool gave.
- Only events the run or search returned, each with its source; the Detail column only from the row (no added
  context such as financials or timelines the row doesn't give); no inferred intent or invented contacts.
- Leave a row out only for scope (trigger type, industry, geography, window), never for source quality or your own
  doubts; two rows about the same event count once ("1 duplicate merged").
- A trigger the user didn't ask for (e.g. an acquisition when they asked for funding and hires) goes under "dropped",
  not in the table.
- Contact details are out of scope; outreach to people in the EU or UK needs a lawful basis.
- Ongoing: on request, `create_monitor(company_list_id=<id>, query=<triggers>, schedule={"every": "day", "at": "08:00", "tz": "<tz>"})`.

## Before you send
Check each line; fix the answer where one fails.
- [ ] The first line gives scope, triggers, window, the run's row count and the rows in the table.
- [ ] Each row has company, trigger, date, detail from the row, why now, and the source link.
- [ ] Dropped events are listed with a count and the reason.

## Done when
The user has a ranked, sourced list with a "why now" per company, and knows what was dropped and why.
