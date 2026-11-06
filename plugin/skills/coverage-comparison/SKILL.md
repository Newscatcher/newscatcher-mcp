---
name: coverage-comparison
description: "Use when the user asks how different countries, languages, regions or outlets cover the same story: framing, emphasis, what each side leaves out, local versus international press, state media versus independent. Compares coverage side by side with NewsCatcher's multilingual search and translated headlines."
---

# Coverage comparison

How the same story reads in different places, with examples from each.

Runs on the NewsCatcher MCP tools (see the `newscatcher` skill for setup, costs and errors).

## Ask first (only what you can't infer)
- The story, and the groups to compare: countries (e.g. US vs China vs Germany), languages, or named outlets.
- The window. Default: the last 7 days.

## Run
1. Find the story: `search_news(query="<story>", window="7d", group="story")`; keep the main story id.
2. One search per group, in its language when you know the local wording:
   `search_news(query="<story in that language>", countries=["CN"], window="7d", limit=15)`
   or `search_news(query="<story>", languages=["de"], window="7d", limit=15)`
   or `search_news(query="<story>", sources=["reuters.com","apnews.com"], window="7d")`.
   Titles and summaries come back with English translations.
3. Volume per group (optional): `count_articles(queries=["<story keywords>"], from="<start>", countries=["US"])`, one
   call per group, to show who paid the most attention.
4. Check the overlap: `get_story(story_id=…)` lists which newsrooms covered the main story.

## Deliver
A table: group · headline framing (2–3 translated headlines) · what they stress · what they leave out · links.
Then a short paragraph on the biggest differences. Quote headlines as translated and mark them "[translated]".

## Quality bar
- Compare like with like: the same days and the same story, not different events.
- Describe framing from headlines and summaries you saw; don't infer motives.
- Name thin groups ("only 2 Brazilian outlets covered it").

## Done when
Each group has at least 2 sourced examples or an explicit "little or no coverage", and the differences are summarised.
