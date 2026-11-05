# Changelog

## [Unreleased]

### Added
- Claude Code plugin in `plugin/` (53 skills, a `news-researcher` subagent) that connects to the hosted server with
  the user's key (`userConfig`, kept in the OS keychain) sent as `x-api-key`; marketplace at the repo root, so users
  install with `/plugin marketplace add Newscatcher/newscatcher-mcp` then `/plugin install newscatcher@newscatcher`.
  Codex and Cursor manifests share the skills and `plugin/mcp.json`.
- `get_research`: `exclude_rows` (row numbers to leave out after checking; the table and the counts line then cover
  only the kept rows, row numbers kept) and `sort="importance"` (most important first, then newest). The critical
  skills use both (company monitoring, cyber, event datasets).
- Instructions: a window without an end ends today; this hosted server has no file tools, so tables are paged with
  `get_research` and the full file comes from the NewsCatcher platform.
- Tests: skill and plugin lint (`tests/test_skills.py`: frontmatter, size, wording, every tool and parameter a skill
  names exists on the hosted server or is a known local-only one, manifests point at the hosted URL), and a lint
  against dollar amounts in descriptions, schemas, instructions and skills.
- PostHog settings aligned with agent-service: `POSTHOG_ENABLED` (default `true`; `false` turns analytics off even
  with a key), `POSTHOG_APP` (default `newscatcher-mcp`) and `POSTHOG_ENVIRONMENT` (default Vercel's
  `VERCEL_TARGET_ENV`, else `local`), sent as `app` / `environment` on every event.

### Changed
- Prices only in credits: `start_research(dry_run=true)` no longer prints a dollar figure next to credits
  ("4,500 credits", not "4,500 credits ($4.50)"). Rule from the CEO: never mention $, only credits.
- Search results print the newsroom count as its own label, `39 newsrooms (story <id>)` (was `story <id> (39
  newsrooms)`), so models copy the count from the right result; results without a story say `1 newsroom`.
- The counts line reads "Counts over all N rows shown in this result".
- `POSTHOG_HOST` is now a bare host (default `us.i.posthog.com`) with a separate `POSTHOG_PORT`, like agent-service.
- Package folder renamed `newscatcher_mcp/` → `src/` (the repo already carries the name).
- API base URLs split into host / port / endpoint env vars (`NEWSCATCHER_{NEWS,AGENT}_API_{URL,PORT,ENDPOINT}`), so
  Vercel Preview can point at the DEV APIs and Production at PROD. A full URL in a `*_URL` var fails at startup.
- Configuration lives in Vercel environment variables; no Doppler project needed.

### Fixed
- Vercel build failed with `PYTHON_ENTRYPOINT_NOT_FOUND`: `server.py` set `app` in a tuple assignment
  (`mcp, app = create_app(...)`), which Vercel's entrypoint detection does not see. `app` is now a plain assignment.
- `scripts/smoke_test.py` crashed silently on Windows consoles (non-UTF-8 code page).

## [0.1.0] - 2026-11-05

### Added
- Python/FastMCP port of the TypeScript NewsCatcher MCP server (`Reseach/newscatcher-mcp`): 15 tools in 4 toolsets
  (news, research, lists, monitors), 2 guide resources, 3 prompts. Tool names, descriptions, defaults and output
  wording match the original.
- Vercel deployment: stateless Streamable HTTP at `/mcp`, `/health`, `vercel.json` (300 s).
- Per-call time budget (`NEWSCATCHER_MAX_CALL_SECONDS`): `count_articles`, `list_articles(tally)`, `get_research` and
  `start_research(wait_seconds)` answer with what they have instead of being cut off by the platform time limit.
- Structured JSON logging with a tracking id per tool call; upstream calls logged by path only.
- Optional PostHog MCP analytics with HMAC-pseudonymised caller ids.
- `?tools=` toolset selection and `?client=` usage tag per connection.
- Unit and HTTP tests ported from the TypeScript suite, CI workflow, live smoke-test script.

### Security
- The hosted server never falls back to a server-side key: each HTTP request must carry the caller's key
  (`x-api-key` or `Authorization: Bearer`). The TypeScript version used `NEWSCATCHER_API_KEY` for keyless HTTP callers.
- `?apiKey=` accepted only with `NEWSCATCHER_ALLOW_KEY_IN_URL=1`. POST without a key → 401 with `WWW-Authenticate`.
- Unexpected errors return a tracking id, not internals.

### Changed (vs the TypeScript server)
- Local-file features (`export_research`, `save_as`, `csv_path`) are not offered (the TS server hid them over HTTP too).
- A timed-out Agent API write now also says "the request may have gone through".
- `cancel_research` retries on 5xx (cancelling twice is safe).
- Explicit `null` is accepted for every optional list parameter.
