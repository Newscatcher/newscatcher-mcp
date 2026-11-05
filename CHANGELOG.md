# Changelog

## [Unreleased]

### Added
- PostHog settings aligned with agent-service: `POSTHOG_ENABLED` (default `true`; `false` turns analytics off even
  with a key), `POSTHOG_APP` (default `newscatcher-mcp`) and `POSTHOG_ENVIRONMENT` (default Vercel's
  `VERCEL_TARGET_ENV`, else `local`), sent as `app` / `environment` on every event.

### Changed
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
