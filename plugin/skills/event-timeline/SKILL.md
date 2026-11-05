---
name: event-timeline
description: "Use when the user wants a timeline, chronology or 'how did this unfold' for one event, saga, scandal, deal, crisis or court case: what happened when, who reported each turn first, and what changed. Builds a dated, sourced timeline from news stories with NewsCatcher."
---

# Event timeline

A dated list of the turns in one saga, each with its first report and a link.

Runs on the NewsCatcher MCP tools (see the `newscatcher` skill for setup, costs and errors).

## Ask first (only what you can't infer)
- The event and its start: "since the deal was announced", "the last 3 months". Default: the last 30 days.
- How fine-grained: major turns only (default) or every development.

## Run
1. Map the saga: `search_news(query="<event in plain words>", window="30d", group="story", limit=30)`. Each story id is one
   development; the newsroom count shows how big it was.
2. For each development that matters, `get_story(story_id=…, limit=10)`: take the date from the earliest credible article
   (the tool lists the earliest ones; a live blog can carry an older timestamp than the event, so check the headline).
3. Older than 30 days: `list_articles(query="\"<key name>\" AND (<key terms>)", from="<start>", to="<end>", sort="oldest", search_in=["title"], page_size=50)`
   and page with the fixed `to` the tool prints.
4. Find the turning points the first pass missed: one `search_news` per phase with other wording
   ("<event> lawsuit", "<event> regulator", "<event> response").

## Deliver
| Date (UTC) | What happened | First reported by | Coverage | Link |
One row per development, oldest first. Then 2–3 sentences: where it stands now and what to watch next.

## Quality bar
- Dates are publication dates of the earliest credible report; say "reported on" rather than "happened on" unless the
  article states the event date.
- Merge duplicates: one development = one row, even when many outlets covered it.
- Mark single-source rows ("1 newsroom") so the reader can weigh them.

## Keep it running
For an ongoing saga, `create_monitor(companies=[…], query="<event>")` when it centres on companies, or rerun this skill
weekly.

## Done when
Every major turn from the start date to today has a dated row with a link, and the current state is stated.
