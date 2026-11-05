# CLAUDE.md

Guidance for Claude Code in this repository.

## What this is

The NewsCatcher MCP server (Python, FastMCP 4) for the News API (`/search`, `/articles`, `/stories`,
`/subscription`) and the Agent API (runs, batches, company lists, monitors). Deployed on Vercel (`server.py:app`).
The design and its evidence live in the CEO's TypeScript original in `Reseach/newscatcher-mcp` (`DESIGN.md`,
`STATUS.md`): read those before changing tool behaviour. `Reseach/` is git-ignored reference material.

## Rules

- **Tool names, descriptions, parameter descriptions and output wording were tuned against model evals.** Change
  them deliberately, never as a side effect, and keep descriptions ≤ 2,048 chars and the instructions < 4,096
  (tests enforce both, plus a banned-wording list: no "full text", no "v4", nothing about reading whole articles).
- **Never use a server-side key for HTTP requests.** Keys come from the caller (`x-api-key` / `Authorization: Bearer`).
  `NEWSCATCHER_API_KEY` is for local stdio only. A test guards this.
- **Never retry Agent API writes after a 5xx or timeout** (`POST /runs`, `/monitors`, lists): no idempotency keys, a
  retry can start a second paid run. Reads and news searches retry.
- **Never log keys, queries or other user content.** Log tool name, tracking id, status, duration, Correlation-ID.
- Long tools must respect the call's time budget (`call.time_left()`, `call.wait_budget()`) and answer with partial
  results; Vercel kills the function at `maxDuration`.
- Optional list parameters: put size limits on the list (`items(X, max_length=n) | None`), never on the outer
  `Optional` (wrong schema node, and explicit `null` fails).
- New tools: write `async def handler(call: Call, ...) -> str` and decorate with `register(...)` in
  `src/tools/`; raise `UserError` for fixable input, let `ApiError` propagate.
- No internal SDK dependency: logging is copied in (`src/log.py`), so the repo installs from public PyPI.
- Docstrings on every function. Update `CHANGELOG.md` with every change.
- **Prices only in credits**, never in currency (a lint fails on `$<digit>` and "dollar").
- **Skills in `plugin/skills/` are tuned like tool descriptions.** A skill may only name tools and parameters the
  hosted server has (or the known local-only ones); `tests/test_skills.py` enforces it. Renaming a tool or a
  parameter means updating the skills that use it. Run `claude plugin validate ./plugin` after manifest changes.

## Commands

```bash
pytest -q                                            # all tests, upstream mocked
NEWSCATCHER_API_KEY=… python scripts/smoke_test.py      # live, read-only, ~6 credits
python server.py --http                              # local HTTP on :8000/mcp
```

## Known environment quirk

On the development machine, HTTP responses to POSTs over loopback arrive with a `transfer-encoding: chunked` header
but an unchunked body (reproduced with a bare Starlette app, unrelated to this code; PyPI downloads showed the same
corruption). Local `--http` testing with a real MCP client fails there; use the in-process tests
(`tests/test_http.py`) or a deployed preview. Vercel does not use uvicorn.
