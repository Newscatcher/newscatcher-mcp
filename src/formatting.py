"""Output helpers.

Every tool answers with compact text (high signal per token, ids next to names) or, with ``format="json"``, compact
JSON with null and empty values dropped. No ``structuredContent``: clients put the text in context, so a structured
copy would double the payload.
"""

from __future__ import annotations

import json
import re
from typing import Any

_WS = re.compile(r"\s+")
_ISO = re.compile(r"^(\d{4}-\d{2}-\d{2})(?:[T ](\d{2}:\d{2}))?")


def num(n: int | float) -> str:
    """Format a number with thousands separators (en-US style).

    Args:
        n (int | float): The number.

    Returns:
        str: e.g. ``"1,234"``.
    """
    if isinstance(n, float) and n.is_integer():
        n = int(n)
    return f"{n:,}"


def plural(n: int, one: str, many: str | None = None) -> str:
    """``"1 article"`` / ``"1,234 articles"``.

    Args:
        n (int): Count.
        one (str): Singular noun.
        many (str | None): Plural noun (default: singular + "s").

    Returns:
        str: The phrase.
    """
    return f"{num(n)} {one if n == 1 else (many or one + 's')}"


def clip(value: Any, n: int) -> str:
    """Flatten whitespace and cut to ``n`` characters with an ellipsis.

    Args:
        value (Any): Text (None becomes "").
        n (int): Maximum length.

    Returns:
        str: The clipped text.
    """
    t = _WS.sub(" ", str(value if value is not None else "")).strip()
    return t[: n - 1].rstrip() + "…" if len(t) > n else t


def when(iso: Any) -> str:
    """``"2026-11-04T19:34:03+00:00"`` → ``"2026-11-04 19:34 UTC"``; date-only strings pass through.

    Args:
        iso (Any): An ISO timestamp.

    Returns:
        str: The short form, or "" for empty input.
    """
    if not iso or not isinstance(iso, str):
        return ""
    m = _ISO.match(iso)
    if not m:
        return iso
    return f"{m.group(1)} {m.group(2)} UTC" if m.group(2) else m.group(1)


def prune(value: Any) -> Any:
    """Drop None, empty strings, empty lists and empty dicts, recursively.

    Args:
        value (Any): Any JSON-like value.

    Returns:
        Any: The pruned value (None when nothing is left of a scalar).
    """
    if isinstance(value, list):
        return [p for p in (prune(v) for v in value) if p is not None]
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in value.items():
            p = prune(v)
            if p is None or p == "" or p == [] or p == {}:
                continue
            out[k] = p
        return out
    return value


def to_json(value: Any) -> str:
    """Compact JSON of the pruned value.

    Args:
        value (Any): The payload.

    Returns:
        str: JSON text.
    """
    return json.dumps(prune(value), ensure_ascii=False, separators=(",", ":"), default=str)


def cell(value: Any) -> str:
    """Render one table cell value as text.

    Args:
        value (Any): The value.

    Returns:
        str: Text.
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def table(columns: list[str], rows: list[dict[str, Any]], max_cell: int = 160) -> str:
    """A Markdown table; cells are flattened to one line and clipped.

    Args:
        columns (list[str]): Column names.
        rows (list[dict[str, Any]]): Rows.
        max_cell (int): Longest cell.

    Returns:
        str: The table.
    """
    head = "| " + " | ".join(columns) + " |"
    sep = "|" + "|".join("---" for _ in columns) + "|"
    body = ["| " + " | ".join(clip(cell(r.get(c)), max_cell).replace("|", "\\|") for c in columns) + " |" for r in rows]
    return "\n".join([head, sep, *body])


def to_list(value: str | list[str] | None) -> list[str] | None:
    """Normalise a list given as a list or one comma-separated string; empty becomes None.

    Args:
        value (str | list[str] | None): The input.

    Returns:
        list[str] | None: Trimmed non-empty items, or None.
    """
    if value is None:
        return None
    items = value if isinstance(value, list) else value.split(",")
    out = [s.strip() for s in items if s and s.strip()]
    return out or None
