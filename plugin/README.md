# NewsCatcher plugin

News search and the NewsCatcher research agent for AI coding assistants. The plugin connects your assistant to the
hosted NewsCatcher MCP server (`https://mcp.newscatcherapi.com/mcp`) and adds skills for common news tasks.

The same folder serves Cursor (`.cursor-plugin/`), Claude Code (`.claude-plugin/`) and Codex (`.codex-plugin/`).

## What's included

- **MCP server** with 15 tools: ranked news search in every language over the last 30 days, every matching article
  over 12 months with exact totals, article counts over time, full coverage of one story, and the research agent for
  verified event tables, company news, company lists and monitors.
- **53 skills**: briefings, company and people research, risk and adverse media, deals and events, sales and PR,
  data and building. You don't call skills by name. Ask for the task and the assistant loads the matching skill.
- **`news-researcher` agent**: runs research that takes several searches and returns a short, cited brief.

## Setup

You need a NewsCatcher API key. Create one at https://platform.newscatcherapi.com. Tool calls draw on the same
credit balance as the API.

### Cursor

1. Install **NewsCatcher** from the Cursor Marketplace (Customize > Plugins).
2. Set the `NEWSCATCHER_API_KEY` variable in the dashboard under **Plugins > NewsCatcher > Configure**.
3. Open a new chat and ask: "Check my NewsCatcher account." This calls the free `get_account` tool and shows your plan
   and balance.

### Claude Code

```text
/plugin marketplace add Newscatcher/newscatcher-mcp
/plugin install newscatcher@newscatcher
```

Claude Code asks for your API key once and keeps it in your system keychain.

### Codex

Set your key in the `NEWSCATCHER_API_KEY` environment variable, then install the plugin from this repository.

## Example prompts

- What were the biggest stories about Nvidia this week? Cite sources.
- Compare daily coverage of OpenAI and Anthropic over the last 30 days. When did each one spike, and why?
- Build a table of layoffs announced by US tech companies in the last 30 days, with company, number of jobs and source.

## Credits

`search_news` costs 1, 5 or 10 credits by effort, `get_story` 1 and `list_articles` 5 per call. Research agent runs
and monitors are charged like API runs. Ask for a dry run ("how much would this cost?") to get a free estimate.
`get_account`, `get_research`, `cancel_research` and the company list tools are free.

## Links

- Documentation: https://www.newscatcherapi.com/docs/integrations/mcp
- Support: support@newscatcherapi.com
- Privacy policy: https://www.newscatcherapi.com/company/legal/privacy-policy
- Terms of service: https://www.newscatcherapi.com/company/legal/terms-of-service
- License: MIT
