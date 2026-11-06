"""Live smoke test against the real NewsCatcher APIs with your key. Read-only; costs about 6 credits.

Usage:
    NEWSCATCHER_API_KEY=<your key> python scripts/smoke_test.py

Calls: get_account (free), search_news effort=low (1 credit), list_articles count_only (5 credits),
get_research list (free), get_company_list (free), get_monitor (free). Exit code 0 when every call succeeded.
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastmcp import Client  # noqa: E402

from src.config import load_config  # noqa: E402
from src.server import build_server  # noqa: E402

CALLS = [
    ("get_account", {}),
    ("search_news", {"query": "Nvidia earnings", "effort": "low", "limit": 3, "window": "3d"}),
    ("list_articles", {"query": "Nvidia", "count_only": True, "from": "7d"}),
    ("get_research", {"limit": 3}),
    ("get_company_list", {}),
    ("get_monitor", {}),
]


async def main() -> int:
    """Run each call and report.

    Returns:
        int: Number of failed calls.
    """
    # Windows consoles default to a legacy code page that can't print "·" or "→".
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    if not os.getenv("NEWSCATCHER_API_KEY"):
        sys.stderr.write("Set NEWSCATCHER_API_KEY first.\n")
        return 1
    failures = 0
    async with Client(build_server(load_config())) as client:
        for name, args in CALLS:
            result = await client.call_tool(name, args, raise_on_error=False)
            status = "FAIL" if result.is_error else "ok"
            failures += bool(result.is_error)
            sys.stdout.write(f"\n=== {status} {name} {args}\n{result.content[0].text[:1200]}\n")
    sys.stdout.write(f"\n{len(CALLS) - failures}/{len(CALLS)} calls succeeded.\n")
    return failures


if __name__ == "__main__":
    sys.exit(1 if asyncio.run(main()) else 0)
