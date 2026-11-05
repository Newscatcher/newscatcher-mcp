---
name: fact-check
description: "Use when the user wants to check whether something really happened or was reported — verify a claim, rumour, quote, viral post or headline against news coverage, find who reported it first, and whether reputable outlets confirm or debunk it. Produces a verdict with the supporting and contradicting coverage."
---

# Fact check against the news

Was it reported, by whom, how widely, and does the coverage support the claim?

Runs on the NewsCatcher MCP tools (`search_news`, `list_articles`, `get_story`). If missing, see the `newscatcher` skill.

## Ask first (only if missing)
- The exact claim (who, what, when). Split compound claims into checkable parts.
- Rough date, if the claim is older than 30 days.

## Run
1. Restate the claim as a neutral search: `search_news(query=<claim in plain words>, window="30d", effort="high", limit=15)`.
   Also search the denial angle: `search_news(query=<claim> + " denied OR false OR fact check")`.
2. Exact wording (quotes, figures, names): `list_articles(query="\"<quoted phrase>\"", from=<date or 30 days ago>)` —
   the exact count shows whether a phrase circulates at all.
3. For the main supporting story, `get_story(story_id)`: earliest report, number of newsrooms, which outlets.
4. Older than 30 days: `list_articles` with `from`/`to` around the date (up to 12 months back).

## Verdict scale
- **Confirmed**: several independent, reputable newsrooms report it as fact.
- **Reported, unconfirmed**: one outlet or unnamed sources; others cite it.
- **Disputed**: credible reporting on both sides, or an official denial.
- **No coverage found**: nothing in the window — say what you searched; absence is not proof it is false.
- **Debunked**: outlets report it as false, with reasons.

## Deliver
Verdict, one-paragraph reasoning, then two lists: supporting coverage and contradicting/denial coverage, each item with
outlet, date and link. Note the earliest report and whether later stories just repeat it.

## Quality bar
- Count newsrooms, not articles: 30 copies of one wire story are one source.
- Quote the claim's key number or phrase exactly as the outlets did.
- No verdict stronger than the evidence.

## Done when
The user has a verdict they could defend with the linked coverage.
