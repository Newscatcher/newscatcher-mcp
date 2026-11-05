# NewsCatcher MCP — production Python port

Source of ideas: `Reseach/newscatcher-mcp/server` (CEO's TypeScript server, 16 tools, 111 tests).
Source of structure: `news-mcp` and `Github-NewsMCP/newsmcp` (FastMCP on Vercel).

## Decisions
- Python + FastMCP 4.x (same pins as news-mcp: fastmcp 4.1.3, mcp 2.2.0), deployed on Vercel as `server.py:app`.
- Hosted HTTP only for now (stateless). Local stdio still works for development (`python server.py`).
- Auth: the user's NewsCatcher Platform key on every request (`x-api-key` / `Authorization: Bearer`).
  `?apiKey=` only behind `NEWSCATCHER_ALLOW_KEY_IN_URL=1`. No server-side key over HTTP. No `api_key` tool argument.
- Tool names, descriptions, defaults, error hints and output text kept identical to the TS server.
- Local-file features not offered (hidden in TS hosted mode too).
- Per-call time budget `NEWSCATCHER_MAX_CALL_SECONDS` (240) under Vercel `maxDuration` (300).
- Logging: no internal SDK (user decision, 2026-11-05) — same JSON shape copied into `src/log.py`.
- PostHog analytics as in newsmcp (optional, HMAC identity).

## Steps
- [x] Project skeleton: `server.py`, `src/` package, requirements, pyproject, vercel.json, .gitignore
- [x] config, HTTP client, formatting, lenient input
- [x] news tools: search_news, list_articles (+tally), count_articles, get_story, get_account
- [x] research tools: start_research (+dry_run), get_research, cancel_research
- [x] lists tools: save_company_list, get_company_list, edit_company_list
- [x] monitor tools: create_monitor, get_monitor, get_monitor_updates, update_monitor
- [x] guides + prompts; instructions; `?tools=` toolset filter
- [x] auth middleware (401/413), /health, PostHog
- [x] tests (67) ported from `server.test.ts` + HTTP/auth/time-budget/key-leak tests
- [ ] live smoke test with a real key (user: `NEWSCATCHER_API_KEY=… python scripts/smoke_test.py`)
- [x] README, CHANGELOG, CLAUDE.md, CI workflow, Dockerfile + docker-compose

## Review
- 67/67 tests pass (mocked upstream). Every ported TS test that applies to hosted mode is covered; the
  file-export, skills and report-renderer tests were not ported (those features are not in the hosted server).
- Real APIs reached end to end with a fake key: News API and Agent API both answer 401, rendered with Correlation-ID
  and the fix. Success path needs a real key (smoke script).
- Bugs found while porting and fixed: Optional-list size limits on the wrong schema node (rejected explicit null);
  operator-precedence bug in Bearer parsing (would accept any scheme).
- Environment issue (not code): loopback POST responses arrive with a broken chunked framing on this machine,
  reproduced with a bare Starlette app. Local `--http` + real client can't be tested here; in-process HTTP tests cover it.
- Not done / open: live smoke test, Vercel project + Doppler setup, OAuth, moving plugin/skills from `Reseach/`.
