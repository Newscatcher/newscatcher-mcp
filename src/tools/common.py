"""Tool registration: every tool call gets a tracking id, the caller's key, a client and one error contract.

Handlers are written as ``async def handler(call: Call, <params>) -> str``. ``register`` exposes them to FastMCP
with the same parameters (``call`` replaced by FastMCP's ``Context``) and turns failures into ``isError`` results
the agent can act on: API errors with a hint, input mistakes with the fix, anything else with a tracking id.
"""

import inspect
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from fastmcp import Context, FastMCP
from fastmcp.tools import ToolResult
from mcp.types import TextContent

from src.auth import request_integration, resolve_key
from src.client import Api, ApiError, NewsCatcherClient, error_hint
from src.config import Config
from src.log import setup_logging

logger = setup_logging(__name__)

# Seconds kept back from the call's time budget for the last API call and the answer.
_WRAP_UP_S = 15.0


class UserError(ValueError):
    """A request the agent can fix; the message says how."""


@dataclass
class Call:
    """What a handler gets for one tool call."""

    client: NewsCatcherClient
    config: Config
    ctx: Context | None
    tracking_id: str

    async def progress(self, done: float, total: float | None, message: str) -> None:
        """Send a progress notification when the client asked for progress; never fails the call.

        Args:
            done (float): Units done.
            total (float | None): Units in all, when known.
            message (str): What is happening.
        """
        if self.ctx is None:
            return
        try:
            await self.ctx.report_progress(done, total or None, message)
        except Exception as exc:  # noqa: BLE001 - progress is best effort, whatever the transport does
            logger.debug("Progress notification failed", extra={"tracking_id": self.tracking_id, "error": type(exc).__name__})

    def time_left(self) -> float:
        """Seconds left in this call's time budget, keeping time back to answer.

        Returns:
            float: Seconds (may be negative).
        """
        return self.client.time_left() - _WRAP_UP_S

    def wait_budget(self, requested: float) -> float:
        """How long this call may wait for a run, given what the agent asked for and the time budget.

        Args:
            requested (float): Seconds the agent asked to wait.

        Returns:
            float: Seconds to wait (0 or more).
        """
        return max(0.0, min(float(requested), self.time_left()))


def text_result(text: str, is_error: bool = False) -> ToolResult:
    """A text-only tool result.

    Args:
        text (str): The answer.
        is_error (bool): Mark as an error result.

    Returns:
        ToolResult: The result.
    """
    return ToolResult(content=[TextContent(type="text", text=text.strip())], is_error=is_error)


def failure_text(err: ApiError, api: Api) -> str:
    """The error text for an API error: status, message, Correlation-ID and what to do.

    Args:
        err (ApiError): The error.
        api (Api): Which API raised it.

    Returns:
        str: The text.
    """
    hint = error_hint(err, api)
    cid = f" (Correlation-ID {err.correlation_id})" if err.correlation_id else ""
    return f"NewsCatcher error {err.status}: {err.message}{cid}" + (f"\n{hint}" if hint else "")


Handler = Callable[..., Awaitable[str]]


def register(
    mcp: FastMCP,
    config: Config,
    *,
    name: str,
    title: str,
    description: str,
    toolset: str,
    api: Api,
    annotations: dict[str, bool],
    always_load: bool = False,
) -> Callable[[Handler], Handler]:
    """Decorator that registers a handler as an MCP tool.

    Args:
        mcp (FastMCP): The server.
        config (Config): Server settings.
        name (str): Tool name.
        title (str): Human title.
        description (str): What the model reads to pick the tool.
        toolset (str): One of ``news``, ``research``, ``lists``, ``monitors`` (used by ``?tools=``).
        api (Api): Which API the tool mainly calls (for error hints).
        annotations (dict[str, bool]): MCP tool annotations.
        always_load (bool): Ask Claude Code to load the tool upfront even when it defers tools.

    Returns:
        Callable[[Handler], Handler]: The decorator (returns the handler unchanged).
    """

    def decorate(handler: Handler) -> Handler:
        """Wrap and register the handler.

        Args:
            handler (Handler): ``async def handler(call: Call, **params) -> str``.

        Returns:
            Handler: The same handler.
        """
        sig = inspect.signature(handler)
        params = [p for p in sig.parameters.values() if p.name != "call"]
        params.append(inspect.Parameter("ctx", inspect.Parameter.KEYWORD_ONLY, annotation=Context))

        async def tool_fn(**kwargs: Any) -> ToolResult:
            ctx: Context | None = kwargs.pop("ctx", None)
            return await run_tool(config, name, api, handler, kwargs, ctx)

        tool_fn.__name__ = name
        tool_fn.__doc__ = description
        tool_fn.__signature__ = sig.replace(parameters=params, return_annotation=ToolResult)  # type: ignore[attr-defined]
        tool_fn.__annotations__ = {p.name: p.annotation for p in params} | {"return": ToolResult}
        mcp.tool(
            tool_fn,
            name=name,
            title=title,
            description=description,
            tags={toolset},
            annotations={"title": title, "openWorldHint": True, **annotations},
            meta={"anthropic/alwaysLoad": True} if always_load else None,
            output_schema=None,
        )
        return handler

    return decorate


async def run_tool(
    config: Config, name: str, api: Api, handler: Handler, kwargs: dict[str, Any], ctx: Context | None
) -> ToolResult:
    """Run one tool call with its own client, tracking id, time budget and error contract.

    Args:
        config (Config): Server settings.
        name (str): Tool name.
        api (Api): Which API the tool mainly calls.
        handler (Handler): The handler.
        kwargs (dict[str, Any]): Validated arguments.
        ctx (Context | None): FastMCP context.

    Returns:
        ToolResult: The answer, or an isError result.
    """
    tracking_id = str(uuid.uuid4())
    started = time.monotonic()
    key = resolve_key(config)
    log = {"tracking_id": tracking_id, "tool": name, "authenticated": bool(key)}
    logger.info(f"Started tool call {name}", extra=log)
    is_error = True
    try:
        async with NewsCatcherClient(
            config,
            key,
            tracking_id=tracking_id,
            integration=request_integration(config),
            deadline=started + config.max_call_seconds,
        ) as client:
            text = await handler(Call(client=client, config=config, ctx=ctx, tracking_id=tracking_id), **kwargs)
        is_error = False
        return text_result(text)
    except ApiError as err:
        log.update(status_code=err.status, error_code=err.code, correlation_id=err.correlation_id)
        return text_result(failure_text(err, api), is_error=True)
    except UserError as err:
        log.update(error_code="invalid_request")
        return text_result(f"Error: {err}", is_error=True)
    except Exception:
        logger.exception(f"Tool call {name} raised an unexpected error", extra=log)
        return text_result(
            f"Error: something went wrong inside the NewsCatcher MCP server (tracking id {tracking_id}). "
            "Retry once; if it fails again, report the tracking id.",
            is_error=True,
        )
    finally:
        log.update(duration_ms=int((time.monotonic() - started) * 1000), is_error=is_error)
        logger.info(f"Finished tool call {name}", extra=log)
