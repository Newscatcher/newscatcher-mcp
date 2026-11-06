---
name: person-profile
description: "Use when the user asks what the news says about a person: an executive, founder, politician, investor, athlete or public figure; recent coverage, roles, statements, controversies, career moves, or a pre-meeting brief. Builds a sourced news profile with NewsCatcher and handles namesakes."
---

# Person profile

What the news says about one person, recent first, with links.

Runs on the NewsCatcher MCP tools (see the `newscatcher` skill for setup, costs and errors).

## Ask first (only what you can't infer)
- Who exactly: full name plus an anchor (company, role, country) so namesakes can be ruled out.
- Why: a meeting brief, due diligence, or a reputation check. It sets the window and depth (default 30 days; due
  diligence: 12 months).

## Run
1. Recent coverage: `search_news(query="\"<Full Name>\" <anchor>", window="30d", group="story", limit=20)`.
2. Exact mentions and older coverage: `list_articles(query="\"<Full Name>\" AND (\"<company>\" OR \"<role>\")", from="<12 months ago>", search_in=["title"], page_size=50)`.
   `count_only=true` first if you only need the volume.
3. Risk angle (due diligence): `search_news(query="\"<Full Name>\" lawsuit OR investigation OR fraud OR resign OR scandal", window="30d")`
   and the same words in `list_articles` over 12 months. For a full screen use the `adverse-media-screening` skill.
4. Attention over time (optional): `count_articles(queries=["\"<Full Name>\""], from="<6 months ago>", interval="month")`.

## Deliver
- One line: who they are now (role, organisation), from the latest coverage.
- Recent news: 3–7 bullets with date, outlet and link.
- Roles and moves, statements that drew coverage, controversies (each sourced), and a coverage trend if you counted.
- "Not found": what you searched for and did not find.

## Quality bar
- Every item must match the anchor; drop namesakes and say how many you dropped.
- Report allegations as allegations, with the outlet that made them.
- No personal details beyond what the coverage is about (no home address, family, health).

## Keep it running
For an executive, `create_monitor(companies=["<their company domain>"], query="<Full Name>")`.

## Done when
The brief answers who they are now and what the news has said recently, every claim linked, namesakes excluded.
