# Changelog

## [Unreleased]

## [0.4.0] - 2026-11-25

Needs Agent API 1.19.2.

### Added
- More rows for a finished events run. `start_research` takes `continue_run_id` and `add_rows` (default 50, up to
  100, the plan's rows per run; a run reaches 1,000 rows). It reads the run and sends `POST /runs/{id}/continue`
  with `max_rows`, the run's new total; like every paid Agent API write it is never retried after a 5xx or timeout.
  The answer gives the continuation id to follow with `get_research` and the most it can cost: only the 50-row
  blocks the new rows start beyond the run's paid ones. `dry_run` shows that cost, the balance and whether the run
  can be continued, for free. Giving `query` or companies with `continue_run_id` is refused (the run keeps its own
  query, mode and columns).
- `get_research` shows continuing: on a run that found every row it asked for (`continuable`), a hint with the
  `start_research(continue_run_id=…)` call; a continuation in progress; what earlier continuations added and how
  many of their rows were already in the run. On a continuation it points to the run it adds rows to.
- Advice for the continuation error codes `run_not_continuable`, `run_busy`, `max_rows_too_low` and
  `max_rows_too_high` (a 409 there is not "the run is still going").
- Monitor listings mark the account's free monitor (the API's `free`).
- `llms-install.md`: setup steps for AI agents (such as Cline) that install MCP servers from the repository. It
  points them at the hosted endpoint instead of a local install, with the Cline `streamableHttp` config.
- README: connection steps for Hermes Agent (`config.yaml`, sign-in or key) and OpenClaw (`openclaw mcp add` with
  Streamable HTTP and sign-in).

### Changed
- `start_research` `max_rows` takes 50 or 100 (was 50, 100, 150 or 200): 100 is the most a run may ask for, so
  150 and 200 were refused by the API (`too_many_rows`). Larger numbers are capped at 100; for more rows, continue the
  run. The same limit caps `add_rows`.
- A continuation dry run on a run that cannot be continued says why and stops: no time, cost or balance lines.
- Skills: `agent-api-integration` documents `POST /runs/{id}/continue`, the run's continuation fields and the
  monitor `free` field; `event-dataset` names continuing among the next steps.
- README: connection examples use the hosted server `https://mcp.newscatcherapi.com/mcp` instead of a
  `<deployment>` placeholder, with a note to swap in your own URL when self-hosting. The intro mentions sign-in
  alongside API keys.

### Fixed
- A slow upstream no longer leaves a tool call without an answer. Retries of reads and searches (after 429, 502,
  503, 504 or a network error) are made only while the call's time budget (`NEWSCATCHER_MAX_CALL_SECONDS`) leaves room
  for them, and each attempt's timeout is capped at the time left (at least 5 s). Before, three slow 5xx answers
  could take the call past the platform's function limit, which ended it with no answer at all; now the error comes
  back, with its Correlation-ID.
- `get_research(format="json")` leaves out `cost_usd` from a run's continuations: the API's processing cost, not
  a price, and prices are given in credits only.

## [0.3.0] - 2026-11-23

Needs Agent API 1.17.0.

### Added
- Search and paging when listing monitors and company lists. `get_monitor` and `get_company_list` take `search`
  (name or topic; for lists also a company's name or domain, so "which list has Stripe?"), `limit` (up to 100 a
  page) and `cursor`, sent as the Agent API's `q`, `limit` and `cursor`. A paged listing ends with "Showing N of
  total" and the next cursor. Without them the listing is unchanged.
- Webhooks. `start_research` and `create_monitor` take `webhook_ids` (up to 20, from the NewsCatcher Platform's
  Webhooks page) and send them as the Agent API's `webhook_ids`; the monitor `keep_updated` creates gets the run's
  webhooks. `dry_run` and the start message say where the results go. A run whose monitor could not get its
  webhooks says so (`keep_updated.webhooks_error`).
- `resend_results` tool: sends a finished run's, or a monitor run's, results to its webhooks again
  (`POST /runs/{id}/webhooks/deliver`, `POST /monitors/{id}/webhooks/deliver`), to all of them or one `webhook_id`.
- Error advice for the webhook codes (`webhook_not_found`, `webhook_not_allowed`, `too_many_webhooks`,
  `webhook_not_attached`, `no_webhooks`, `nothing_to_send`, `run_in_progress`, `resend_too_soon`, `not_allowed`),
  where the status alone would be explained wrongly (a 403 read as a plan limit, a 409 read as "still running").
- Instructions: one line on webhooks.

### Fixed
- A 429 `resend_too_soon` is not retried: the resend is allowed once a minute per webhook, so a retry cannot succeed.

### Changed
- `get_research` on a company run (or batch) starts with a summary from the API's `company_counts`,
  `companies_failed` and `outcome`, e.g. "38 of 40 done: 31 found, 5 no news, 2 failed (not charged) · outcome:
  partial", and notes that a partial run still counts as succeeded. `companies_failed` alone is enough to explain
  missing news and offer a rerun. Runs without these fields render as before.
- Company run timing follows the account's company queue (about 3 companies at a time across all of an account's
  company runs and monitors): new time text, and `start_research(dry_run=true)` estimates the time from the number
  of companies and says that starting several company runs at once is not faster.
- While a company run is going, pending companies are described as queued for a free place, not stuck, and a long
  wait for a big list is called normal (wait or refresh, rather than cancel).
- A failed run says it was not charged and to try again (in a few minutes when the news search did not work),
  instead of "No rows". A company run with no rows no longer suggests rephrasing or `mode=standard`.
- Skills: `company-watchlist` timing; `agent-api-integration` documents `company_counts`, `companies_failed`,
  `outcome`, webhooks and resend; `news-alerts-integration` offers Platform webhooks before polling code.

## [0.2.1] - 2026-11-16

### Changed
- `get_research` on a company run explains companies that got no news because the run did not finish them
  (`news_status` `out_of_time`, `model_unavailable`, `internal_error`, `failed` or `not_searched`), says their news
  is missing rather than empty, and names the `start_research(companies=[…])` call that runs them again.
- `start_research(dry_run=true)` with more than 50 typed companies says the run goes in parts of 50; only a saved
  list of more than 50 still runs as a batch of several runs.

## [0.2.0] - 2026-11-12

### Security
- CI workflow runs with a read-only GitHub token (`permissions: contents: read`).

### Fixed
- A 403 for a key that belongs to another NewsCatcher product no longer adds the "plan does not include this"
  advice: the API's own message already says what to do.

### Added
- Sign-in with a NewsCatcher platform account (OAuth 2.1), off unless `NEWSCATCHER_OAUTH=1` with
  `NEWSCATCHER_PUBLIC_URL` and `NEWSCATCHER_SUPABASE_URL` set (`NEWSCATCHER_PLATFORM_API_*` optional). MCP clients get
  a Connect button: a 401 names the protected-resource document, which names this server as the authorization server;
  its metadata is the auth project's with `issuer` and `registration_endpoint` rewritten here. Documents are served at
  the path-suffixed and bare locations and under the OIDC name. `POST /oauth/register` forwards dynamic registration,
  registering clients that name no `token_endpoint_auth_method` as public (`none`). `GET /` names the MCP endpoint.
- A Bearer value shaped like a JWT is a platform access token: it is exchanged for the Default API Key of the user's
  default workspace through the platform API (which also validates it), cached in memory for five minutes per token,
  one lookup shared by concurrent requests. A rejected token gets 401 `invalid_token`; a signed-in user with no
  workspace or key gets tool errors that say what to do. API keys work exactly as before; `x-api-key` wins over a
  token.
- A token the platform API rejects is logged with the API's reason and whether the token was issued to a connected
  app or had expired (never the token).
- Clients are steered off the `openid` scope: the 401 challenge and the protected-resource document name
  `email profile offline_access`, and the served authorization-server metadata drops `openid`. An auth project that
  signs with a shared secret (HS256) cannot issue the ID token `openid` implies, so the token request failed after
  approval.
- Cursor Marketplace listing for the plugin: `.cursor-plugin/marketplace.json` at the repo root, and in the Cursor
  manifest a `NEWSCATCHER_API_KEY` variable (the placeholder `plugin/mcp.json` already uses), `logo` and
  `repository`. New `plugin/assets/logo.png` and `plugin/README.md` (setup for Cursor, Claude Code and Codex).
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
