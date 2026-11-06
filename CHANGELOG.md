# Changelog

## [Unreleased]

### Added
- MIT `LICENSE` (the plugin manifest already declared MIT); `license` in `pyproject.toml`, License section in the README.

## [0.1.0] - 2026-11-06

First public release.

### Added
- MCP server for the NewsCatcher News API and research agent: 15 tools in 4 toolsets (news, research, lists,
  monitors), 2 guide resources and 3 prompts.
  - `search_news`, `list_articles` (with `tally` by outlet, author, country or language), `count_articles`,
    `get_story`, `get_account`.
  - `start_research` (with a free `dry_run` estimate), `get_research` (with `exclude_rows` and
    `sort="importance"`), `cancel_research`.
  - `save_company_list`, `get_company_list`, `edit_company_list`.
  - `create_monitor`, `get_monitor`, `get_monitor_updates`, `update_monitor`.
- Hosted deployment on Vercel: stateless Streamable HTTP at `/mcp`, `/health`.
- Claude Code plugin in `plugin/` (53 skills, a `news-researcher` subagent) that connects to the hosted server with
  the user's key, kept in the OS keychain. Install with `/plugin marketplace add Newscatcher/newscatcher-mcp`, then
  `/plugin install newscatcher@newscatcher`. Codex and Cursor manifests share the skills.
- Per-call time budget (`NEWSCATCHER_MAX_CALL_SECONDS`): long tools answer with what they have before the platform
  time limit.
- `?tools=` selects toolsets and `?client=` tags usage, per connection.
- API hosts configured as host / port / endpoint (`NEWSCATCHER_{NEWS,AGENT}_API_{URL,PORT,ENDPOINT}`), so preview and
  production deployments can target different API environments.
- Structured JSON logging with a tracking id per tool call; upstream calls logged by path only.
- Optional PostHog analytics (`POSTHOG_ENABLED`, `POSTHOG_APP`, `POSTHOG_ENVIRONMENT`, `POSTHOG_HOST`,
  `POSTHOG_PORT`) with HMAC-pseudonymised caller ids.
- Tests (tools, rendering, HTTP and auth, analytics, skill and plugin lint), a CI workflow and a live smoke-test script.

### Security
- Every HTTP request must carry the caller's own key (`x-api-key` or `Authorization: Bearer`); the server never falls
  back to a key of its own. A POST without a key gets 401 with `WWW-Authenticate`.
- `?apiKey=` on the URL is accepted only with `NEWSCATCHER_ALLOW_KEY_IN_URL=1`.
- Agent API writes are never retried after a 5xx or timeout, so a retry cannot start a second paid run.
- Keys, queries and other user content are never logged; unexpected errors return a tracking id, not internals.
