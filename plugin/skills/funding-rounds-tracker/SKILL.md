---
name: funding-rounds-tracker
description: "Use when the user wants startup or company funding rounds — who raised, how much, from whom, at what stage — for a sector, geography, stage or investor, over a period; for VC deal flow, market maps, sales prospecting or competitor tracking. Builds a funding-rounds table from the news with the NewsCatcher research agent and can keep it updated."
---

# Funding rounds tracker

Who raised money, how much, at what stage, from whom and when, with a source per round.

Runs on the NewsCatcher MCP tools (`start_research`, `get_research`, `export_research`, `create_monitor`). If missing,
see the `newscatcher` skill.

## Defaults (say them in your first line)
- Window: as asked ("this month" = since the 1st, "October 2026" = Oct 1–31, "last 30 days"); default the last 30
  days. When "this month" is only a few days old, say so.
- Geography: as asked, else worldwide. Stage: as asked, else all stages. Sector: as asked.
- One fast research run (3–10 minutes, about 1,000 credits; `dry_run=true` shows the cost).

## Run
1. `start_research(query="<Stage> funding rounds raised by <sector> startups in <geography> announced between <start> and <end>, with company, amount, currency, round, lead investor, other investors, announcement date and source", mode="fast", max_rows=50)`.
   For one investor: "Funding rounds led or joined by <investor> announced between <start> and <end>, with …".
   For "every round" or a big market, `max_rows=100`.
2. `get_research(run_id, wait_seconds=300)` until it finishes; if you must stop first, give the run id and ask the user
   to say "refresh". Its "Counts over all N rows" line gives rounds by stage, investors in 2+ rows (any role) and the
   disclosed amounts summed per currency: use it for the summary instead of paging through every row.
3. `export_research(run_id, file_format="csv")` when the user wants the full table.

## Deliver
1. First line: scope, window and "<n> rounds found".
2. Table, newest first, at most 10 rows (the most important or newest; say how many more there are and where: the run or the file):

   | Date | Company | Round | Amount (as reported) | Lead investor | Other investors | Source |

   Newest first. Amount exactly as reported with currency; "undisclosed" when absent. Source = the row's source
   URL as a link; never link the company's own domain as the source.
3. Summary, from the counts line (it covers all the run's rows; if you dropped rows, say the kept count separately):
   - Rounds: count by stage, and how many disclosed an amount.
   - Total disclosed: per currency, as the counts line gives it (don't convert unless you state the rate).
   - The three largest rounds, compared within one currency (or say "in USD" and the rate you used).
   - Most active investors: the "investors in 2+ rows" list, with counts ("no investor in two or more rounds" is a
     valid answer).
4. One line of next steps: the full CSV, a wider window, or a weekly update with
   `create_monitor(from_run_id=run_id)` if they want to keep tracking.

## Quality bar
- Stages: keep the stages asked. A sub-round (A1, A2, an extension) counts as the stage it extends; label it as such.
- Report plainly: only what the tool results say. No added causes, motives or labels ("main driver", "full licence",
  "positive tone"); if you give your own read, mark it as your read.
- A number appears only if a tool printed it or you counted it from rows you show; don't recompute a total a tool gave.
- One row per round (the same round is reported by many outlets); an extension is its own round.
- Date = announcement date; rows outside the window are dropped and counted.
- Every company, amount and investor comes from the run's rows; never add rounds from memory.
- Fewer rows than expected: say so and suggest a wider window or `mode="standard"`.

## Before you send
Check each line; fix the answer where one fails.
- [ ] The first line gives scope, window and the number of rounds.
- [ ] Rows are newest first; amounts as reported with currency; the source link is the row's source URL.
- [ ] Totals per currency and the most active investors come from the counts line.
- [ ] The next-steps line is there.

## Done when
The table covers the scope and window, the summary is computed from the rows, and every round has a source.
