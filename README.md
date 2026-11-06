# NewsCatcher MCP

MCP server for the NewsCatcher **News API** (search, exact counts, stories) and the **research agent** (verified
event datasets, company news, company lists, monitors). Hosted on Vercel as stateless Streamable HTTP; every user
brings their own NewsCatcher Platform API key. 

Tool names, descriptions, defaults and output wording were tuned against model evals: change them deliberately.

## Connect

Get an API key at [platform.newscatcherapi.com](https://platform.newscatcherapi.com).

**Claude Code**

```bash
claude mcp add --transport http newscatcher https://<deployment>/mcp --header "x-api-key: YOUR_KEY"
```

**Cursor / any MCP client** (`mcp.json`)

```json
{
  "mcpServers": {
    "newscatcher": {
      "type": "http",
      "url": "https://<deployment>/mcp",
      "headers": { "x-api-key": "YOUR_KEY" }
    }
  }
}
```

`Authorization: Bearer YOUR_KEY` works as well. Clients that cannot send headers (claude.ai custom connectors) need
`?apiKey=YOUR_KEY` on the URL, which is off unless the deployment sets `NEWSCATCHER_ALLOW_KEY_IN_URL=1` (keys in URLs
end up in access logs). OAuth will replace this.

**Options on the URL**

- `?tools=news` (or `news,research`) exposes only those toolsets, to save context. Default: all.
- `?client=cursor` tags usage in the upstream User-Agent.

### Claude Code plugin (tools + 53 skills)

```bash
/plugin marketplace add Newscatcher/newscatcher-mcp
/plugin install newscatcher@newscatcher
```

Claude Code asks for the NewsCatcher API key once and keeps it in the OS keychain; the plugin connects to
`https://mcp.newscatcherapi.com/mcp` with it. The skills (`plugin/skills/`) cover briefings, adverse media, company
monitoring, sales triggers, deal, funding and layoff trackers, share of voice, PR coverage, earnings, cyber incidents
and more; each one tells the model which tools to call and how to present the result. They were tuned against an
end-to-end eval (37 of the 39 critical-skill test prompts at 4+ of 5 with Claude Haiku 5.5).

## Tools

| Toolset | Tool | What it does | Cost |
|---|---|---|---|
| news | `search_news` | Ranked, story-grouped search over the last 30 days, any language | 1 / 5 / 10 credits (effort) |
| news | `list_articles` | Every article matching a boolean query, 12 months, exact total; `tally` by outlet/author/country/language | 5 per call |
| news | `count_articles` | Daily/weekly/monthly counts for 1–5 queries, share of voice | 5 per bucket × query (max 60) |
| news | `get_story` | All coverage of one story: newsrooms, earliest articles | 1 |
| news | `get_account` | Plan, balance, limits | free |
| research | `start_research` | Research agent run: events dataset or company news; `dry_run` estimates cost free | per run |
| research | `get_research` | Wait for a run and show its table; list runs | free |
| research | `cancel_research` | Stop a run (not charged) | free |
| lists | `save_company_list` / `get_company_list` / `edit_company_list` | Reusable company lists | free |
| monitors | `create_monitor` / `get_monitor` / `get_monitor_updates` / `update_monitor` | Scheduled updates, only what is new | per run / per company |

Also: two guide resources (`newscatcher://guides/query-syntax`, `newscatcher://guides/research-agent`) and three
prompts (`news_briefing`, `company_watch`, `event_dataset`).

Not in the hosted server: the local-file features of the original (`export_research`, `save_as`, `csv_path`). The
instructions tell models so; some skills mention them for local setups.

`get_research` also takes `exclude_rows` (leave out rows after checking; counts cover the kept rows) and
`sort` (`newest`, `oldest`, `importance`).

## Example

A raw MCP call (after `initialize`), e.g. with curl:

```bash
curl -X POST https://<deployment>/mcp \
  -H "x-api-key: YOUR_KEY" -H "content-type: application/json" \
  -H "accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"search_news","arguments":{"query":"Nvidia guidance","window":"2d","effort":"low"}}}'
```

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `NEWSCATCHER_MAX_CALL_SECONDS` | `240` | Longest one tool call works (waiting for a run, paging, counting) before answering with what it has. Keep below Vercel `maxDuration` (300 in `vercel.json`). |
| `NEWSCATCHER_ALLOW_KEY_IN_URL` | off | `1` accepts `?apiKey=` on the MCP URL. |
| `NEWSCATCHER_TOOLSETS` | all | Default toolsets when the URL has no `?tools=`. |
| `NEWSCATCHER_NEWS_API_URL` | `api.newscatcherapi.com` | News API **host** only (no `https://`, no path). |
| `NEWSCATCHER_NEWS_API_PORT` | – (443) | News API port. |
| `NEWSCATCHER_NEWS_API_ENDPOINT` | `news-api` | News API base path. |
| `NEWSCATCHER_AGENT_API_URL` | `api.newscatcherapi.com` | Agent API **host** only. |
| `NEWSCATCHER_AGENT_API_PORT` | – (443) | Agent API port. |
| `NEWSCATCHER_AGENT_API_ENDPOINT` | `agent` | Agent API base path. |
| `NEWSCATCHER_TIMEOUT_MS` | `90000` | Timeout per upstream request. |
| `NEWSCATCHER_INTEGRATION` | – | Default User-Agent tag. |
| `LOG_LEVEL` | `INFO` | JSON logs (Stackdriver shape). |
| `POSTHOG_PROJECT_API_KEY` | – | Enables PostHog MCP analytics (write-only `phc_…` key). |
| `POSTHOG_ENABLED` | `true` | `false` turns PostHog off completely, even with the key (e.g. on dev). |
| `POSTHOG_APP` / `POSTHOG_ENVIRONMENT` | `newscatcher-mcp` / Vercel's `VERCEL_TARGET_ENV`, else `local` | Sent as `app` and `environment` on every event, so one PostHog project can hold several apps and environments. |
| `POSTHOG_HOST` / `POSTHOG_PORT` | `us.i.posthog.com` / `443` | PostHog ingestion host (region) and port. |
| `POSTHOG_IDENTITY_SALT` | – | Secret for pseudonymous caller ids (HMAC of the key). Without it callers stay anonymous. |
| `NEWSCATCHER_API_KEY` | – | **Local stdio only.** Never used for HTTP requests. Do not set it on Vercel. |

URLs are split into host / port / endpoint; the scheme is always https and defaults point at the
PROD APIs. The only secrets are the two optional PostHog values.

## Deploy (Vercel)

Vercel's Python runtime serves the module-level `app` in `server.py`; `vercel.json` gives the function 300 s.
Push to the connected branch, or `vercel deploy`. Check `https://<deployment>/health` → `{"ok": true, "version": …}`.

Set the variables in **Vercel → Project → Settings → Environment Variables**, per environment:

| Vercel environment | API it talks to | What to set |
|---|---|---|
| Production | PROD | nothing for the APIs (defaults), PostHog values if wanted |
| Preview (branches / PRs) | DEV | `NEWSCATCHER_NEWS_API_URL/PORT/ENDPOINT` and `NEWSCATCHER_AGENT_API_URL/PORT/ENDPOINT` → DEV hosts |

Never set `NEWSCATCHER_API_KEY` on Vercel: users bring their own keys.

## Run locally

```bash
python -m venv .venv && .venv/Scripts/activate   # or source .venv/bin/activate
pip install -r requirements-test.txt

python server.py                                  # stdio, key from NEWSCATCHER_API_KEY
python server.py --http                           # HTTP on http://127.0.0.1:8000/mcp, key per request
docker compose up --build                         # same, in Docker, on http://localhost:8000/mcp
```

## Test

```bash
pytest -q                                         # unit + HTTP tests, upstream mocked, no key needed
NEWSCATCHER_API_KEY=… python scripts/smoke_test.py   # live, read-only, ~6 credits
```

## Layout

```
server.py                      Entrypoint: module-level `mcp` and `app` (Vercel), stdio / --http locally
src/
  server.py                    build_server / create_app, instructions, toolset + input-error middleware
  auth.py                      Key per request, 401 middleware, ?tools= / ?client=
  client.py                    HTTP client: retries, pacing, no retry of paid writes, error hints
  config.py, log.py            Settings; structured JSON logging
  formatting.py, lenient.py    Compact text output; lenient list/object input
  analytics.py                 Optional PostHog
  guides.py                    Guide resources and prompts
  tools/                       news, research, lists, monitors (+ common registration, shared params)
tests/                         Tools, rendering, HTTP/auth, analytics, skill lint
```
