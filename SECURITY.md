# Security Policy

## Reporting a vulnerability

Please report security issues privately, not in public issues or pull requests.

Use GitHub's private reporting: open the repository's **Security** tab and choose **Report a vulnerability**. Include
what you found, how to reproduce it, and the impact you expect. We aim to acknowledge reports within 3 business days
and to keep you updated until the issue is resolved. Please give us a reasonable time to fix it before disclosing it.

## Supported versions

Only the latest release on `main` and the hosted server at `https://mcp.newscatcherapi.com/mcp` receive security
fixes.

## Scope

In scope:

- The MCP server in this repository and its hosted deployment (authentication, key handling, request handling,
  data exposure between callers).
- The Claude Code plugin in `plugin/` (manifests, skills, scripts).

Out of scope: the NewsCatcher APIs themselves (report those to NewsCatcher support), findings that need a stolen API
key or a compromised client machine, denial of service by volume, and reports from automated scanners without a
working proof of concept.

## How keys are handled

- Each request to the hosted server must carry the caller's own NewsCatcher API key (`x-api-key` or
  `Authorization: Bearer`). The server holds no key of its own and never falls back to one.
- Keys are forwarded only to the NewsCatcher APIs. They are never logged, never returned in tool results, and never
  sent to analytics; analytics, when enabled, uses a salted one-way hash of the key.
- Keys in the URL (`?apiKey=`) are rejected unless the operator explicitly enables them, because URLs end up in logs.
- With sign-in on, a caller may send a platform access token instead of a key. The server never verifies or stores
  signing secrets: the platform API checks the token and returns the caller's workspace key, which is held in memory
  for at most five minutes, keyed by a SHA-256 of the token. Tokens and keys are never logged. A token the platform
  rejects gets 401 `invalid_token`; a token is never forwarded to the APIs as a key.

If you believe your API key was exposed, rotate it in the [NewsCatcher platform](https://platform.newscatcherapi.com).
