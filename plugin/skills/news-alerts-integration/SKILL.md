---
name: news-alerts-integration
description: "Use when the user wants to build news alerts into their own code or tools: send NewsCatcher monitor updates or new matching articles to Slack, Teams, email, a webhook, a database or a ticket queue on a schedule. Shows working code against the NewsCatcher Agent and News REST APIs: polling monitors, deduplicating, and posting."
---

# News alerts integration

Code that turns NewsCatcher monitors or searches into alerts in the user's own channel.

Uses the REST APIs directly; set `NEWSCATCHER_API_KEY` in the environment (never hard-code it).
- Agent API: `https://api.newscatcherapi.com/agent` (monitors, runs). News API: `https://api.newscatcherapi.com/news-api`.
- Header: `x-api-key: $NEWSCATCHER_API_KEY`.

## Ask first (only what you can't infer)
- What to alert on: a company monitor (stories per company), a dataset monitor (new table rows), or a keyword query.
- Where to send (Slack incoming webhook, email, HTTP endpoint), how often, and where the code runs (cron, serverless).

## Pick the source
| Alert on | Create once | Poll |
|---|---|---|
| Companies | `create_monitor(companies=[…] or company_list_id=…)` (or POST `/monitors`) | GET `/monitors/{id}/runs?limit=5`, then GET `/monitors/runs/{run_id}`: `stories[]` (each `story`, `company`, `update`) |
| A research table | `create_monitor(from_run_id=…)` | GET `/monitors/runs/{run_id}`: `rows[]` with `change` = new or update |
| Keywords | nothing | POST `/news-api/articles` with `from_date` = last check, `sort_by="published_at"` |

The Agent API has no push webhooks: poll on the monitor's schedule (a little after its run time) and remember the last
run id you processed.

## Code (Python, Slack)
```python
import os, json, pathlib, requests
KEY = os.environ["NEWSCATCHER_API_KEY"]; SLACK = os.environ["SLACK_WEBHOOK_URL"]
AGENT = "https://api.newscatcherapi.com/agent"; H = {"x-api-key": KEY}
STATE = pathlib.Path("last_run.json")

def latest_succeeded_run(monitor_id):
    runs = requests.get(f"{AGENT}/monitors/{monitor_id}/runs", headers=H, params={"limit": 5}, timeout=30).json()["runs"]
    return next((r for r in runs if r["status"] == "succeeded"), None)

def main(monitor_id):
    seen = json.loads(STATE.read_text()) if STATE.exists() else {}
    run = latest_succeeded_run(monitor_id)
    if not run or seen.get(monitor_id) == run["run_id"]:
        return  # nothing new
    detail = requests.get(f"{AGENT}/monitors/runs/{run['run_id']}", headers=H, timeout=30).json()
    lines = []
    for item in detail.get("stories", []):           # company monitors
        s = item["story"]
        lines.append(f"*{item.get('company', s.get('domain'))}*: {s['headline']} ({s.get('first_date', '')})")
    for row in detail.get("rows", []):                # dataset monitors
        lines.append(f"[{row.get('change')}] " + " · ".join(str(v) for k, v in row.items() if k != "change")[:300])
    if lines:
        requests.post(SLACK, json={"text": f"{detail.get('name', 'NewsCatcher')}: {len(lines)} updates\n" + "\n".join(lines[:30])}, timeout=30)
    seen[monitor_id] = run["run_id"]; STATE.write_text(json.dumps(seen))

if __name__ == "__main__":
    main(os.environ["MONITOR_ID"])
```

## Code (TypeScript, keyword alert since the last check)
```ts
const KEY = process.env.NEWSCATCHER_API_KEY!;
const since = process.env.LAST_CHECK ?? new Date(Date.now() - 3600_000).toISOString();
const res = await fetch("https://api.newscatcherapi.com/news-api/articles", {
  method: "POST",
  headers: { "x-api-key": KEY, "content-type": "application/json" },
  body: JSON.stringify({ q: '"Acme Corp" AND (recall OR lawsuit)', from_date: since, sort_by: "published_at", page_size: 50 }),
});
if (!res.ok) throw new Error(`NewsCatcher ${res.status}: ${await res.text()}`);
const { results, total_hits } = await res.json();
for (const a of results) console.log(a.published_at, a.source?.name, a.title, a.url); // post these to your channel
```

## Quality bar
- Deduplicate: store processed run ids (monitors) or article ids/urls (keywords).
- Back off on 429 (honour Retry-After) and alert on 401/402 so a dead key or empty balance is noticed.
- `/articles` allows about 1 request a second on smaller plans; keep polls sequential.
- Keep secrets in env or a secret manager.

## Done when
The user has runnable code, a schedule, and a test message delivered from a real monitor run or query.
