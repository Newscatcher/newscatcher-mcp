---
name: media-outreach-targets
description: "Use when the user wants to find which outlets and journalists cover a topic, beat, company or competitor — for PR pitching, media lists, analyst relations or understanding who shapes coverage — ranked by how often and how recently they wrote about it. Produces an outlet and author list with example articles from NewsCatcher."
---

# Media outreach targets

Who writes about this topic, how often, and their most relevant recent pieces.

Runs on the NewsCatcher MCP tools (`list_articles`, `search_news`). If missing, see the `newscatcher` skill.

## Run
1. Who writes about it: `list_articles(query=<precise topic query>, from="30 days ago", tally="author", tally_pages=5)`.
   The tool counts the newest 500 matches by byline (people only; agencies and desks are left out) and gives each
   author's outlets and latest article. Widen `from` (up to 12 months) for niche beats.
2. Which outlets: the same call with `tally="source"`. Add `top_sources="top 100 US"` (or another country) to keep
   to major publishers, or `countries=[…]` for a market.
3. Competitor angle: the same tallies for `"<Competitor>" AND <topic>` to see who covers your competitors.
4. Check the top 10 authors: `search_news(query="<author name> <topic>", window="30d")` or `list_articles(query="<topic>", sources=["<outlet>"], from="30 days ago")`
   to read their angle from recent headlines.

## Deliver
Ranked table: outlet · rank · author · articles on the topic (window) · latest article (date, headline, link) · angle
(one line). Then outlets that cover the topic without bylines.

## Quality bar
- Bylines are as published; "Staff", "Reuters" and agency names are not people.
- Contact details are out of scope.

## Done when
The user has a ranked list of outlets and authors with evidence of their coverage.
