# Lessons

## Don't add the internal SDK to small services by default (2026-11-05)
The global CLAUDE.md says "use v3_internal_sdk", but for this MCP the user chose not to: it needs the private GitLab
index (install time, a token in the build, a dependency for a server that may go public) just for logging. Rule:
for MCP servers and other small public-facing services, copy the SDK's logging shape into a local module instead of
depending on the SDK; ask before pulling the SDK in for anything else.

## Constraints on Optional[list] in pydantic go on the list, not the Optional
`Annotated[list[X] | None, Field(max_length=n)]` puts `maxLength` on the anyOf wrapper and rejects an explicit
`null`. Write `Annotated[list[X], Field(max_length=n)] | None`. Check the generated JSON schema of every new tool.
