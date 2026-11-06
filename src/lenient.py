"""Lenient input for list and object parameters.

Some clients and models send a list or an object as JSON text (``'["stripe.com","wise.com"]'``,
``'{"every":"week"}'``), a comma-separated string (``"en, de"``) or a single value (``"en"``). These validators turn
those into the real shape before validation, so the call works instead of failing.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BeforeValidator


def parse_json_text(value: Any) -> Any:
    """``'["a","b"]'`` → ``["a","b"]``, ``'{"k":1}'`` → ``{"k":1}``, ``"true"``/``"false"`` → booleans.

    Args:
        value (Any): The raw input.

    Returns:
        Any: The parsed value, or the input unchanged.
    """
    if not isinstance(value, str):
        return value
    s = value.strip()
    if s in ("true", "false"):
        return s == "true"
    if not (s.startswith("[") or s.startswith("{")):
        return value
    try:
        return json.loads(s)
    except ValueError:
        return value


def as_list(value: Any) -> Any:
    """Lists of short tokens (codes, domains): also accept ``"a, b"`` and ``"a"``.

    Args:
        value (Any): The raw input.

    Returns:
        Any: A list when the input was text, else the input.
    """
    p = parse_json_text(value)
    if isinstance(p, str):
        return [x.strip() for x in p.split(",") if x.strip()]
    return p


def as_items(value: Any) -> Any:
    """Lists of phrases that may contain commas (queries, names): JSON text or one value, never split on commas.

    Args:
        value (Any): The raw input.

    Returns:
        Any: A list when the input was text, else the input.
    """
    p = parse_json_text(value)
    if isinstance(p, str):
        return [p] if p.strip() else []
    return p


JsonText = BeforeValidator(parse_json_text)
TokenList = BeforeValidator(as_list)
ItemList = BeforeValidator(as_items)
