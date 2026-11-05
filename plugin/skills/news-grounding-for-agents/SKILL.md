---
name: news-grounding-for-agents
description: "Use when the user is building an AI agent, chatbot or RAG pipeline that must answer with current, cited news — choosing retrieval calls, query rewriting, freshness windows, deduplication by story, citation formats, caching and cost control — or wants their agent to use NewsCatcher as its news tool. Gives the retrieval design and prompt patterns."
---

# News grounding for agents

Fresh, de-duplicated, cited news in the agent's context, at a predictable cost and latency.

Two ways in: the NewsCatcher MCP server (tools `search_news`, `list_articles`, `get_story`; for MCP-capable agents),
or the REST API from your own code (`https://api.newscatcherapi.com/news-api`, header `x-api-key`; define the base URL
once as a constant and copy it exactly). The REST
endpoints behind the tools: `POST /search`, `POST /articles`, `GET /stories/{story_id}`.

## Retrieval design
1. **Route:** news-shaped questions (what happened, latest, is it true, coverage of X) go to NewsCatcher; static facts
   and documentation go to web search or your own corpus.
2. **Rewrite** the user turn into a standalone query with entities and a window: "what did Nvidia say this week?" →
   `{"q": "Nvidia revenue guidance", "search_window": "7d"}`. Resolve pronouns from the conversation first.
3. **Retrieve** with `POST /search`: `effort` low (1 credit, about 4 s) for latency-critical paths, medium (5 credits,
   about 8 s, the default) for most questions, high (10 credits, about 25 s) for hard or ambiguous ones; `limit` 10;
   `collapse: "story"` for one article per event; `search_window` 1 minute to 30 days.
4. **Pack** each result: `title` (and `title_en` when translated), `source.name`, `published_at`, `summary_en` or
   `summary`, `url`, `story.newsrooms`. About 70 tokens per result, so 10 results fit easily.
5. **Answer** only from the packed results, citing as `[Outlet](url)`; when nothing comes back, say "no coverage found
   in the last <window>" instead of answering from memory.
6. **Go deeper** when needed: `GET /stories/{story_id}` (1 credit) for every article of one event; `POST /articles`
   (5 credits per page of up to 100) for exact boolean matching or news up to 12 months old; open an article URL with
   a fetch tool to read it.

## Example: a retrieval function (Python)
```python
import os, requests

def news_context(question: str, window: str = "7d", k: int = 8) -> str:
    """Recent news for a question, as a numbered context block with citations."""
    r = requests.post("https://api.newscatcherapi.com/news-api/search",
                      headers={"x-api-key": os.environ["NEWSCATCHER_API_KEY"]},
                      json={"q": question, "search_window": window, "effort": "medium",
                            "limit": k, "collapse": "story"}, timeout=60)
    r.raise_for_status()
    results = r.json().get("results", [])
    if not results:
        return f"No news coverage found in the last {window}."
    lines = []
    for i, a in enumerate(results, 1):
        title = a.get("title_en") or a["title"]
        summary = a.get("summary_en") or a.get("summary") or ""
        newsrooms = (a.get("story") or {}).get("newsrooms", 1)
        lines.append(f"[{i}] {title} — {a['source']['name']}, {a['published_at'][:10]}, {newsrooms} newsrooms\n"
                     f"    {summary}\n    {a['url']}")
    return "\n".join(lines)
```
Put the block in the prompt under "Sources", and instruct: cite as [n], answer only from the sources, say when they
don't cover the question.

## Example: a `news` tool for an agent framework
```json
{"name": "news_search",
 "description": "Search recent news (last 30 days, every language). Use for current events, latest developments, or checking whether something was reported. Returns headlines, one-line summaries, outlets, dates and links.",
 "parameters": {"type": "object", "properties": {
   "query": {"type": "string", "description": "Standalone query with names and topic, e.g. 'Nvidia export controls China'"},
   "window": {"type": "string", "description": "How far back, any value from 30m to 30d, e.g. 6h, 2d, 7d (default)"},
   "limit": {"type": "integer", "description": "Results, default 8"}},
  "required": ["query"]}}
```
Keep `window` a free string (the API takes anything from 1 minute to 30 days); don't narrow it to a fixed list. The
handler calls `POST /search` as in the Python example and returns the packed block (text, not raw JSON: it costs
fewer tokens and models cite it better). An MCP-capable framework (LangGraph through an MCP adapter, Claude, Cursor,
OpenAI Agents) can instead connect to the NewsCatcher MCP server and get `search_news` and the other tools ready-made.

## Prompt rules for the agent
- Prefer stories covered by more newsrooms; flag single-source claims as such.
- Quote numbers exactly; keep dates absolute (UTC).
- Every link comes from the results; never construct one.

## Cost and caching
- Credits: low 1, medium 5, high 10 per `/search` call; `/stories` 1; `/articles` 5 per page. A 200 with zero results
  is charged; errors are not.
- A typical turn needs one or two searches. Cache identical (query, window, effort) for a few minutes on breaking
  topics, longer for slow ones.
- Keep the key server-side; proxy from browser or mobile apps through your backend.

## Done when
The agent routes news questions to NewsCatcher, answers with citations from the results, handles empty results
honestly, and stays within its token and credit budget.
