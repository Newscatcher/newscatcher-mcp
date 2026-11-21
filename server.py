"""Entrypoint.

- Vercel imports the module-level ``app`` (ASGI, stateless Streamable HTTP at ``/mcp``, ``/health``).
- ``python server.py`` runs over stdio for local development (key from ``NEWSCATCHER_API_KEY``).
- ``python server.py --http`` runs the HTTP app locally with uvicorn on ``PORT`` (default 8000).

``mcp`` and ``app`` must stay module-level with these names, and ``app`` a plain ``app = ...`` assignment: Vercel's
build finds the entrypoint by reading the source, and does not see a tuple assignment (``mcp, app = ...``).
"""

import os
import sys

from src import VERSION
from src.config import load_config
from src.log import setup_logging
from src.server import create_app

logger = setup_logging(__name__)

config = load_config()
mcp, http_app = create_app(config)
app = http_app

logger.info(
    "NewsCatcher MCP server initialized",
    extra={
        "server_version": VERSION,
        "toolsets": sorted(config.toolsets),
        "max_call_seconds": config.max_call_seconds,
        "key_in_url_allowed": config.allow_key_in_url,
        "sign_in": config.oauth is not None,
    },
)


def main() -> None:
    """Run locally: stdio by default, or HTTP with ``--http``."""
    if "--http" in sys.argv:
        import uvicorn

        uvicorn.run(app, host=os.getenv("HOST", "127.0.0.1"), port=int(os.getenv("PORT", "8000")))
    else:
        mcp.run()


if __name__ == "__main__":
    main()
