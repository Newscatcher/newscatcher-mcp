---
name: brand-crisis-monitor
description: "Use when the user wants to monitor a brand, company, product or executive for reputation risk — negative coverage, a developing crisis, backlash, boycotts, safety scares, scandals, viral complaints that reach the press — or needs a crisis situation report: how big it is, where it is spreading, what outlets say. Combines NewsCatcher news search, counts and a monitor."
---

# Brand crisis monitor

Is negative coverage starting, spreading or fading, how big is it, and what exactly is being said, with numbers and
sources.

Runs on the NewsCatcher MCP tools (`search_news`, `get_story`, `count_articles`, `list_articles`, `create_monitor`). If
missing, see the `newscatcher` skill.

## First
- Brand, company, product or person not named ("our CEO")? Ask for the name (and the issue, if unclear) and stop.
  Don't search a guess.
- Defaults: the last 7 days, every language. Say them in your first line, with exact dates ending today.
- Stay on the issue the user named (e.g. a price rise). Stories about a different issue for the same brand (a new
  feature, a lawsuit) go in one separate line, not in the counts or the severity.

## Run (situation report)
1. What is out there: `search_news(query="<Brand> <issue words, e.g. backlash OR criticism OR boycott OR price increase>", window="7d", group="story", effort="high", limit=20)`.
2. The main story (always): the first result of step 1 that is about this issue (skip results on other topics,
   e.g. a product launch when the issue is a price rise). `get_story(story_id)` on it gives its newsroom count, first
   report and latest report. Don't call an outlet the origin unless get_story shows its article first.
3. Volume and trend:
   `count_articles(queries=["\"<Brand>\" AND (<issue words>)", "\"<Brand>\""], from="7d", interval="day")`, which gives
   the issue's daily coverage and its share of all coverage of the brand. Keep the brand name in quotes and the
   issue words specific to this issue (the same words in steps 3 and 4).
4. Tier-1 pickup: `list_articles(query="\"<Brand>\" AND (<issue words>)", from="7d", top_sources="top 100 US", tally="source", tally_pages=2)`
   (or the brand's main market, e.g. "top 100 GB"): its "distinct values" is the number of tier-1 outlets.
5. Spread (optional): step 1 with `languages=[…]` or `countries=[…]` for key markets.

## Rate severity with these rules
- **Low:** one or two newsrooms, no tier-1 outlet, flat or falling daily count.
- **Rising:** the main story has 5+ newsrooms, or the issue's daily count grew two days in a row, or one tier-1
  outlet covers it. A single spike that is already falling is "low, fading".
- **Major:** tier-1 outlets in more than one country, or the issue is a large share (over a third) of the brand's
  coverage for two or more days.

## Deliver
```
<Brand>: <issue> · <window> · severity <low | rising | major> (<the rule it meets>)
Size: <n> articles on the issue (<share>% of all <Brand> coverage) · main story <n> newsrooms (top search result) · tier-1: <n> outlets
Trend: <daily counts, e.g. Nov 1: 12 · Nov 2: 40 · Nov 3: 31>, peak <date>
What is being said: 3–5 bullets, each a claim or angle with the outlet and link; the brand's response if reported
Tone: described from headlines, with 2–3 headline examples (counts are topic matches, not sentiment scores)
Options: respond · keep monitoring · escalate, each with one line on when it fits
```
For ongoing watching, on request: `create_monitor(companies=["<domain>"], query="<issue words>, controversy, backlash, boycott, lawsuit, recall", schedule={"every": "day", "at": "07:00", "tz": "<tz>"})`.

## Quality bar
- Report plainly: only what the tool results say. No added causes, motives or labels ("main driver", "full licence",
  "positive tone"); if you give your own read, mark it as your read.
- A number appears only if a tool printed it or you counted it from rows you show; don't recompute a total a tool gave.
- Every count, newsroom number and link comes from the tool results; say which query produced each count.
- Newsrooms are not articles: get_story shows both; use the newsroom count for size.
- Separate what happened (a decision, a recall, a statement) from commentary and complaints.
- Tone and severity follow the rules above; no guesses about social media reach that the tools don't show.

## Before you send
Check each line; fix the answer where one fails.
- [ ] The main story is the top search result's story, with its newsroom count from get_story.
- [ ] The share figure is the one count_articles printed for the issue query (brand in quotes plus issue words).
- [ ] Tier-1 is the tally's "distinct values" number, unchanged; name outlets as tier-1 only from that tally.
- [ ] If most tier-1 outlets' latest headlines are not about the issue, say the tier-1 count is noisy and don't
      use it for the severity rule.
- [ ] Tone has 2–3 headline examples, each with its link; no conclusions beyond what those headlines say.
- [ ] The window line shows the exact dates of the 7-day window; no share or trend you computed yourself.
- [ ] Every bullet in "What is being said" has a link.
- [ ] The severity names the rule it meets.

## Done when
The user knows how big it is, which way it is going, what is being said and by whom, with numbers and sources.
