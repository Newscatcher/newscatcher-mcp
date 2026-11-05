---
name: agent-api-integration
description: "Use when the user is writing code against the NewsCatcher Agent API — starting research runs (event datasets or company news), polling or streaming progress, reading result tables, exporting CSV/XLSX, managing company lists and monitors, or wiring monitor deliveries into a database, Slack, CRM or spreadsheet. Gives correct endpoints, request bodies, async patterns and error handling."
---

# Build with the NewsCatcher Agent API

Base URL `https://api.newscatcherapi.com/agent` (define it once as a constant and copy it exactly), header
`x-api-key: <key>` (from an environment variable, never in code). Spec: `https://api.newscatcherapi.com/agent/openapi.json`; generate types from it for anything large.

## Endpoints (the ones most code needs)
| Do | Call | Notes |
|---|---|---|
| Start a run | `POST /runs` | `202 {run_id, status, kind}`; a company list bigger than one run allows starts a batch: `batch_id` + `run_ids` |
| Follow it | `GET /runs/{id}` | `status`: queued → running → succeeded, failed or cancelled; `phases` for progress |
| Stream it | `GET /runs/{id}/progress` | Server-Sent Events `run_status`, `run_event`, `run_result`, `run_error`; resume with `Last-Event-ID` |
| Results | `GET /runs/{id}` | `columns`, `rows` (each with a source URL), `companies` (coverage per company), `report` (standard/max) |
| Files | `GET /runs/{id}/export.csv` · `export.xlsx` (the rows, for events and company runs) · `companies.csv` (one row per company, company runs) | after the run succeeds |
| List runs | `GET /runs?limit=20&kind=events` | to find a run after a crash or timeout |
| Batches | `GET /batches/{id}` | `progress {runs_done, runs_total, companies_done, companies_total}`; same export paths |
| Company list | `POST /companies/lists {name, companies, list_id?}` | `companies`: `[{"domain": "stripe.com"}]`; resolution runs in the background (`status: resolving`) |
| Upload a file | `POST /companies/lists/upload` | multipart: `file` (.csv, .xlsx, .json or .txt with one company domain per line or row) and optional `name`, `list_id`; the response lists lines that gave no company |
| List status | `GET /companies/lists/{id}` | `status`: resolving → ready, plus a status per company; a run started on a resolving list waits for it |
| Add / fix | `POST /companies/lists/{id}/companies {companies}` · `PATCH /companies/lists/{id}/companies/{domain}` | |
| Monitor | `POST /monitors {kind, …}` | `kind: "companies"` with `companies` or `list_id` (+ `query`), or `kind: "dataset"` with `from_run_id` |
| List monitors | `GET /monitors` · `GET /monitors/{id}` | settings, schedule, `next_run_at`, `last_run_id` |
| Deliveries | `GET /monitors/{id}/stories?days=7` (companies) · `GET /monitors/{id}/rows` (dataset) | or per run: `GET /monitors/{id}/runs` → `GET /monitors/runs/{run_id}` |
| Pause / resume | `PATCH /monitors/{id} {"enabled": false}` · `{"enabled": true, "fill_gap": true}` | `POST /monitors/{id}/run` runs it now |

## Request bodies
- Events run: `{"query": "Bank M&A deals announced in the US since October 1, 2026", "mode": "fast", "max_rows": 50}`.
  `mode`: fast (minutes) · standard (10–30 min, verified rows, cited briefing) · max. `max_rows`: 50, 100, 150 or 200.
- Company run: `{"companies": {"items": [{"domain": "stripe.com"}], "save_as_list": true, "list_name": "Fintech"}, "query": "funding and acquisitions", "lookback_days": 30}`
  or `{"companies": {"list_id": "<uuid>"}, …}`. `query` blank = every story.
- Keep it updated (monitor created when the run succeeds): `"keep_updated": {"schedule": {"every": "day", "at": "09:00", "tz": "America/New_York"}}`;
  weekly adds `"weekday": 0` (Monday).
- Schedule object everywhere: `every` (day, week, hours), `at` (HH:MM), `tz` (IANA), `weekday` (0 = Monday), `hours`.

## Patterns
- **Runs take minutes:** never block a web request on one. Store `run_id`, then poll from a worker every 15–30 s, or
  stream the SSE endpoint.
- **No idempotency key on POST /runs or /monitors:** persist the id right after the POST; after a timeout or a 5xx,
  check `GET /runs?limit=` (or `GET /monitors`) before posting again, or you may pay for two runs. Company lists accept
  your own `list_id` (a UUID), so retrying that create is safe.
- **Delivery sync:** store the monitor run ids you have processed and handle each once; company stories carry
  `story_id` and `version` (it rises when a story grows): keep the highest version seen per `story_id` and act only
  when a story is new or its version is higher.
- **Errors:** body `{code, message}`. 401 key · 402 credits · 403 plan limit (mode, rows, companies, schedule) ·
  404 id · 409 not ready yet · 422 bad field · 429 back off (`Retry-After`). Retry reads on 429 and 5xx; retry a
  POST only on 429 (it is refused before any work starts), never on a 5xx or timeout.
- **Only these fields:** create a monitor with `kind`, `name`, `companies` or `list_id`, `from_run_id`, `query`,
  `schedule`; change it with `PATCH /monitors/{id}` (`name`, `companies`, `query`, `schedule`, `enabled`, `fill_gap`);
  run it now with `POST /monitors/{id}/run`. The Agent API has no balance endpoint: the credit balance is
  `GET https://api.newscatcherapi.com/news-api/subscription` (same key). Don't use endpoints or fields not listed here
  or in the spec.

## Minimal examples
```python
import os, time, requests
API = "https://api.newscatcherapi.com/agent"
H = {"x-api-key": os.environ["NEWSCATCHER_API_KEY"]}

run = requests.post(f"{API}/runs", headers=H, timeout=60,
                    json={"query": "Layoffs at US tech companies since October 1, 2026", "mode": "fast"}).json()
run_id = run["run_id"]                      # persist this before polling
while True:
    r = requests.get(f"{API}/runs/{run_id}", headers=H, timeout=60).json()
    if r["status"] in ("succeeded", "failed", "cancelled"):
        break
    time.sleep(20)
if r["status"] == "succeeded":
    csv = requests.get(f"{API}/runs/{run_id}/export.csv", headers=H, timeout=120)
    open(f"{run_id}.csv", "wb").write(csv.content)
```
```bash
# Upload companies, then research the list
curl -s -X POST "$API/companies/lists/upload" -H "x-api-key: $NEWSCATCHER_API_KEY" \
  -F "file=@accounts.csv" -F "name=Accounts"            # → {"list_id": "…", "status": "resolving", …}
curl -s -X POST "$API/runs" -H "x-api-key: $NEWSCATCHER_API_KEY" -H "Content-Type: application/json" \
  -d '{"companies": {"list_id": "<list_id>"}, "query": "funding, leadership changes", "lookback_days": 30}'
```
```ts
// Company monitor, then read its new stories every hour
const API = "https://api.newscatcherapi.com/agent";
const H = { "x-api-key": process.env.NEWSCATCHER_API_KEY!, "Content-Type": "application/json" };
const m = await (await fetch(`${API}/monitors`, { method: "POST", headers: H, body: JSON.stringify({
  kind: "companies", companies: [{ domain: "stripe.com" }, { domain: "wise.com" }],
  query: "funding, M&A, leadership changes", schedule: { every: "day", at: "09:00", tz: "UTC" } }) })).json();
// poll hourly (free reads): new stories appear after each scheduled run; act on a story when its version is new or higher
const { stories } = await (await fetch(`${API}/monitors/${m.monitor_id}/stories?days=1`, { headers: H })).json();
```
Schedules more often than every 24 hours are refused with `invalid_schedule` on Free and PAYG plans (Enterprise
allows them); for those plans use `every: "day"` and poll the stories hourly.

## Done when
A run is created, followed to completion without blocking, its rows land where the user needs them, and monitor
deliveries are processed exactly once.
