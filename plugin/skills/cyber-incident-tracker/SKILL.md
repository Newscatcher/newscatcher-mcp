---
name: cyber-incident-tracker
description: "Use when the user wants cybersecurity incidents — data breaches, ransomware attacks, outages, leaks, hacks, vulnerabilities exploited in the wild — affecting companies, a sector, vendors or a region; for threat intelligence, third-party risk, security teams or journalists. Builds an incident table from the news with NewsCatcher and keeps it updated."
---

# Cyber incident tracker

Reported breaches and attacks: who was hit, by what, how badly and when, each with a source and a status.

Runs on the NewsCatcher MCP tools (`start_research`, `get_research`, `export_research`, `search_news`). If missing, see
the `newscatcher` skill.

## Defaults (say them in your first line)
- Window: what the user asked, else the last 30 days; "the last N days" = today minus N days to today, written as
  exact dates in the query. Region: as asked, else worldwide. Incident types: breaches, ransomware, hacks, data leaks,
  attack-caused outages, exploited vulnerabilities.
- One fast research run (3–10 minutes; `dry_run=true` shows the price). If the user can't be asked, run with these defaults.
- Windows over about 60 days: a fast run covers them only partly. Say so in your first line (or use mode="standard").

## Run
**A sector or region (the incident log):**
1. `start_research(query="Cybersecurity incidents (data breaches, ransomware attacks, hacks, data leaks, attack-caused outages) at <sector> organisations in <region> disclosed or reported between <start date> and <end date>, with organisation, country, incident type, threat actor if named, records or systems affected, disclosure date, status (confirmed by the organisation, claimed by a threat actor, or reported by media) and source", mode="fast", max_rows=100)`.
   For windows longer than about 60 days, mode="standard" finds more (10–30 minutes; show its cost with `dry_run=true`),
   or say that a fast run covers the window only partly.
2. `get_research(run_id, wait_seconds=300, sort="newest")` until it finishes. If you must stop first, give the run id
   and ask the user to say "refresh". It shows the 25 newest rows plus a "Counts over all N rows" line (status, threat
   actors, countries, dates) covering every row: build the summary from it instead of paging through the rest.
3. Scope check: list the # of rows outside the asked scope (e.g. clinics when the user asked for hospitals, or not
   ransomware when they asked for ransomware), then `get_research(run_id, wait_seconds=0, exclude_rows=[…], sort="newest")`
   so the table and the counts line cover only the kept rows.
4. "Every" or "all", or more than 10 kept rows: `export_research(run_id, file_format="csv", exclude_rows=[…])` and give
   the path; show 25 rows inline.

**Named vendors or companies (exposure check):**
1. `start_research(companies=[<domains>], query="data breach, ransomware, cyberattack, hack, data leak, outage, exploited vulnerability, security incident", lookback_days=90)`.
2. `get_research(run_id, wait_seconds=300, sort="newest")`; its coverage line shows the companies with no matching news.
3. Keep only incidents where the vendor itself was hit (a breach, attack or outage at the vendor). A vendor's
   research or reports about attacks on others, product news, market moves, and claims the vendor denies are left
   out. State "<k> kept · <n> left out" so that k + n equals the run's row count (recount with
   `get_research(run_id, wait_seconds=0, exclude_rows=[…])` to be sure).
   Table for vendor checks: | Date | Vendor | What happened (from the row's headline) | Outlets | Source |; no status
   column unless the row states one. Source = the row's url as a full link, never just the domain. The first line
   states the scope: the vendors, the window (last 90 days) and worldwide coverage. A vendor that denies being hit,
   or reports on attacks against others, is not an incident at that vendor.

**Today only:** `search_news(query="ransomware OR \"data breach\" OR cyberattack <sector>", window="1d", sort="newest", group="story", limit=20)`.

## Deliver
1. First line: scope and defaults used, and how many incidents the run found (what the news reported, not a census).
2. Table, newest first, at most 10 rows (the most important or newest; say how many more there are and where: the run or the file):

   | Date | Organisation (country) | Type | Threat actor | Impact | Status | Source |

   Date = the row's date column, as the run reports it (say which date it is, e.g. "event date"); newest first.
   "(country)" only when the row gives one; otherwise just the organisation. Status, type and date labels in the
   run's own words. Impact as reported (records, systems, downtime), "not disclosed" when missing;
   threat actor "not named" when absent. Keep only rows in the asked scope (e.g. hospitals, not clinics or labs) and
   say how many rows you left out and why.
3. Summary, from the "Counts over all N rows" line: incidents by status (confirmed, claimed, reported) and type,
   threat actors in two or more rows, countries; plus the three largest impacts among the rows shown. Vendor checks:
   each vendor's incidents, then the vendors with none found.
4. One line of next steps: the full CSV, a longer or deeper run (mode="standard"), or a daily monitor with
   `create_monitor(from_run_id=run_id)` if they want ongoing tracking.

## Quality bar
- Report plainly: only what the tool results say. No added causes, motives or labels ("main driver", "full licence",
  "positive tone"); if you give your own read, mark it as your read.
- A number appears only if a tool printed it or you counted it from rows you show; don't recompute a total a tool gave.
- Every row, date, actor and number comes from the run or search results; totals come from the counts line.
- Keep the answer compact: 25 rows at most, short cells, links copied exactly.
- Status as reported: a ransomware group's claim is not a confirmed breach; say "claimed by <group>".
- Status exactly as the row gives it; don't upgrade a claim to a confirmed incident.
- Fewer rows than expected: say so and suggest a wider window or standard mode; never add incidents from memory.

## Before you send
Check each line; fix the answer where one fails.
- [ ] The first line gives the window as exact dates, the region, and the number of incidents the run found.
- [ ] Rows are newest first by the row's date, at most 10, each with status as reported and a source link.
- [ ] Rows outside the asked scope are left out and counted.
- [ ] The summary numbers come from the "Counts over all N rows" line.
- [ ] The next-steps line is there.

## Done when
In-scope incidents are listed with type, impact, status and source, the summary comes from those rows, and the scope
is stated.
