# Installing NewsCatcher MCP (instructions for AI agents)

NewsCatcher MCP is a **hosted remote server**. Do not clone this repository, install Python packages or run a
local server. Add the hosted endpoint to the client's MCP settings and you are done.

- Endpoint: `https://mcp.newscatcherapi.com/mcp`
- Transport: Streamable HTTP (there is no SSE endpoint)
- Auth: a NewsCatcher API key in the `x-api-key` header. The user gets one at
  https://platform.newscatcherapi.com (API keys page).

## Steps

1. Ask the user for their NewsCatcher API key. If they don't have one, send them to
   https://platform.newscatcherapi.com to sign up and copy a key. Do not invent a key or continue without one.
2. Add this entry under `mcpServers` in the client's MCP settings, with the key in place of `YOUR_API_KEY`.
   Keep any servers that are already there.

### Cline (`cline_mcp_settings.json`)

```json
{
  "mcpServers": {
    "newscatcher": {
      "type": "streamableHttp",
      "url": "https://mcp.newscatcherapi.com/mcp",
      "headers": { "x-api-key": "YOUR_API_KEY" },
      "disabled": false,
      "autoApprove": []
    }
  }
}
```

`"type"` must be exactly `"streamableHttp"` (camelCase). If it is missing or spelled `"streamable-http"`, Cline
falls back to SSE and the connection fails.

### Other clients (`mcp.json`)

```json
{
  "mcpServers": {
    "newscatcher": {
      "type": "http",
      "url": "https://mcp.newscatcherapi.com/mcp",
      "headers": { "x-api-key": "YOUR_API_KEY" }
    }
  }
}
```

Claude Code: `claude mcp add --transport http newscatcher https://mcp.newscatcherapi.com/mcp --header "x-api-key: YOUR_API_KEY"`

## Check it works

Call the `get_account` tool. It is free and returns the plan and credit balance. A `401` means the key is missing or
wrong. Then try `search_news` with a simple query such as `{"query": "Nvidia"}`.

## Options

- Load only some toolsets to save context: append `?tools=news` (or `news,research`, `lists`, `monitors`) to the URL.
- `Authorization: Bearer YOUR_API_KEY` works instead of `x-api-key`.
- Clients that support MCP OAuth can connect without a key: add the URL and sign in with a NewsCatcher account.
