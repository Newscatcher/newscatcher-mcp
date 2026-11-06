---
name: adverse-media-screening
description: "Use when the user needs adverse media or negative news screening — KYC, AML, due diligence, vendor or third-party risk, onboarding checks — on a company or person: fraud, corruption, sanctions, money laundering, lawsuits, regulatory actions, investigations, scandals, in any language. Produces a screening report with findings by risk category, sources and a clear \"no adverse media found\" statement when that is the result."
---

# Adverse media screening

A documented negative-news screen on one subject: what was found, how serious, how well sourced, and exactly what was
searched, so a reviewer can repeat and audit it.

Runs on the NewsCatcher MCP tools (`list_articles`, `search_news`, `start_research`, `get_research`). If missing, see
the `newscatcher` skill.

## Identify the subject first
- Company: legal name, other or former names, country, website domain. Person: full name plus one identifier (role,
  employer, city) to tell namesakes apart.
- Ambiguous name and you can ask: ask one question. Otherwise take the best-known entity that fits what the user gave,
  say which one in your first line, and treat others with the same name as namesakes.
- Only a name, and no domain or country can be found in the results: run a name-based screen, say so, and say that a
  domain, country or registration number would firm up the match.
- Defaults: the last 12 months, every language. Your first line says them, e.g. "Screened: <subject>, last 12
  months, every language".
- Two subjects (e.g. a person and their company): run steps 1–3 for each, add a Subject column to the findings
  table, and give the step 1 total per subject. The Result line's matter count equals the number of table rows.

## Run (in this order)
1. Size it: `list_articles(query=<Q>, from="365 days ago", count_only=true)`, where <Q> is
   `("<Name>" OR "<Other name>") AND (fraud OR bribery OR corruption OR "money laundering" OR sanctions OR sanctioned OR lawsuit OR sued OR investigation OR probe OR indicted OR charged OR convicted OR fine OR fined OR penalty OR scandal OR embezzlement OR raid)`.
   For a person, require the identifier too: `"<Full Name>" AND ("<Employer>" OR "<Role>") AND (…)`.
2. Read the hits: `list_articles(query=<Q>, from="365 days ago", search_in=["title"], sort="relevance", page_size=30)`
   (headline mentions are about the subject), then `list_articles(query=<Q>, from="365 days ago", search_in=["title_body_translated"], sort="relevance", page_size=20)`
   for coverage in other languages.
3. Recent and ranked: `search_news(query="\"<Name>\" fraud OR investigation OR lawsuit OR sanctions OR fine", window="30d", effort="high", group="story", limit=20)`.
   Relevance search returns near matches too: results not about the subject are discarded and counted.
4. Company with a domain: `start_research(companies=["<domain>"], query="legal, regulatory, fraud, sanctions, investigations, lawsuits, fines", lookback_days=365)`,
   then `get_research(run_id, wait_seconds=300)` until it finishes (if you must stop first, give the run id and ask the
   user to say "refresh"). It finds stories about the right entity, with type and importance. It is billed per
   company; `dry_run=true` shows the price first.
5. Sizes: search_news results show newsrooms per story; research rows show `outlets` and `articles`. Report each as
   given ("7 newsrooms", "3 outlets").
6. A call fails (e.g. 503 on the 12-month window)? Screen what still works (the last 30 days) and name the gap.

## Classify each finding
- **Same subject only:** the article matches two identifiers (name plus role, company, country or city). Otherwise it
  is a namesake or an unrelated hit: count it under Discarded. For a company, anything about its own conduct is a
  finding, including charges or trials of its executives over that conduct. Matters about related people or group
  companies that are not about the subject's conduct go in a separate "Related parties" line.
- **Category:** sanctions · fraud, corruption, bribery · money laundering · criminal · regulatory and fines ·
  litigation · other (labour, environment, safety, data protection).
- **Status, as reported:** allegation · investigation · charge · trial · conviction · settlement · fine · dismissed or cleared.
  Never upgrade one: an investigation is not a charge.
- **Severity:** high = sanctions, criminal charges or convictions, findings of fraud; medium = regulator actions, fines,
  formal investigations; low = civil lawsuits, allegations, single unconfirmed reports.

## Deliver
```
Adverse media screen: <Subject> (<identifiers used>)
Scope: <from> → <to> · <languages> · <n> matching articles (the step 1 total) · <r> items read (every result your calls after step 1 returned, research rows included) · research run <id> (if used)
Result: ADVERSE MEDIA FOUND (<n> matters: <h> high, <m> medium, <l> low) | NO ADVERSE MEDIA FOUND

| Date | Category | Severity | Status | What happened | Outlets · newsrooms | Link |
(one row per matter, most severe first, at most 10; short cells; count the rest)

Related parties: <matters about related people or group companies, with links>, or "none"
Discarded: <n> of the headlines read (namesakes, unrelated, duplicates), e.g. "<headline>" (<why>); the rest of the step 1 total was not read
Gaps: <failed calls, thin coverage, languages not covered>, or "none"
Queries: <the exact query strings, fields and windows>
Research support for a human reviewer, not a legal or compliance determination.
```
- One row per matter: twenty articles about one lawsuit are one row (cite the best one or two links).
- No findings is a valid result: say NO ADVERSE MEDIA FOUND plainly, with the scope and how many articles were screened.
- Older matters that articles mention may be listed as background, marked as outside the window.

## Quality bar
- Report plainly: only what the tool results say. No added causes, motives or labels ("main driver", "full licence",
  "positive tone"); if you give your own read, mark it as your read.
- A number appears only if a tool printed it or you counted it from rows you show; don't recompute a total a tool gave.
- Every finding, date, outlet, count and link comes from a tool result in this conversation.
- Claim only the checks you ran: no languages, sources or confirmations you did not search.
- Sizes as the tools give them: newsrooms from search_news, outlets and articles from research rows.
- Keep the whole answer under about 900 words. Status is one of the listed words, nothing else.
- The Queries line is required: the exact query strings, fields and windows of steps 1–3.
- No credit or price figures unless a tool result shows them.

## Before you send
Check each line; fix the answer where one fails.
- [ ] The first line names the subject, the identifiers used, the window and the languages.
- [ ] Scope gives the step 1 total and the number of headlines read, exactly as the tools returned them.
- [ ] Every finding row has a date, category, severity, status as reported, and a link from the results.
- [ ] Related parties, Discarded, Gaps and Queries are all present (write "none" where empty).
- [ ] Nothing in the answer comes from memory: drop any fact you can't point to in a tool result.

## Done when
The subject is identified, each matter is classified and sourced, discarded hits are counted, gaps are named, and the
queries are written down.
