"""Parameter types shared by several tools (lenient lists, boolean queries, schedules, companies)."""

import re
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, BeforeValidator, Field

from src.lenient import TokenList

Format = Annotated[Literal["text", "json"], Field(description="text (default, compact) or json (machine-readable).")]
PlainFormat = Annotated[Literal["text", "json"], Field(description="text (default) or json.")]

SearchInField = Literal[
    "title", "body", "title_body", "summary",
    "title_translated", "body_translated", "title_body_translated", "summary_translated",
]


def items(item: object, *, min_length: int | None = None, max_length: int | None = None) -> object:
    """A list type with its size limits on the list itself.

    Use as ``items(X, max_length=5) | None`` for optional lists: a limit put on the outer ``Optional`` would land on
    the wrong JSON-schema node and make an explicit ``null`` fail validation.

    Args:
        item (object): Item type.
        min_length (int | None): Fewest items.
        max_length (int | None): Most items.

    Returns:
        object: The Annotated list type.
    """
    return Annotated[list[item], Field(min_length=min_length, max_length=max_length)]  # type: ignore[valid-type]


def str_list(description: str) -> object:
    """An optional list of strings that also accepts ``"a,b"``, ``"a"`` or JSON text.

    Args:
        description (str): Parameter description.

    Returns:
        object: The Annotated type.
    """
    return Annotated[list[str] | None, TokenList, Field(description=description)]


def search_in(description: str) -> object:
    """Where a boolean query is matched (at most 2 fields).

    Args:
        description (str): Parameter description.

    Returns:
        object: The Annotated type.
    """
    return Annotated[items(SearchInField, max_length=2) | None, TokenList, Field(description=description)]  # type: ignore[operator]


Languages = str_list('Only these languages: ISO 639-1 codes, e.g. ["en","de"].')
Countries = str_list('Only publishers from these countries: ISO 3166-1 alpha-2 codes, e.g. ["US","GB"].')
Sources = str_list('Only these publishers: domains, e.g. ["reuters.com","ft.com"].')
ExcludeLanguages = str_list("Leave out these languages (ISO 639-1).")
ExcludeCountries = str_list("Leave out publishers from these countries (ISO 3166-1 alpha-2).")
ExcludeSources = str_list("Leave out these publishers (domains).")


def news_filters(
    languages: list[str] | None,
    countries: list[str] | None,
    sources: list[str] | None,
    exclude_languages: list[str] | None,
    exclude_countries: list[str] | None,
    exclude_sources: list[str] | None,
) -> dict[str, list[str] | None]:
    """Map the friendly filter names to the News API's.

    Args:
        languages (list[str] | None): Only these languages.
        countries (list[str] | None): Only these countries.
        sources (list[str] | None): Only these domains.
        exclude_languages (list[str] | None): Not these languages.
        exclude_countries (list[str] | None): Not these countries.
        exclude_sources (list[str] | None): Not these domains.

    Returns:
        dict[str, list[str] | None]: API body fields.
    """
    return {
        "languages": languages or None,
        "countries": countries or None,
        "sources": sources or None,
        "not_languages": exclude_languages or None,
        "not_countries": exclude_countries or None,
        "not_sources": exclude_sources or None,
    }


_BAD_CHARS = re.compile(r"[\[\]/\\:^]")
_TOKENS = re.compile(r'"[^"]*"|\(|\)|[^\s()"]+')


def mixes_and_or(q: str) -> bool:
    """True when AND and OR appear side by side in one parenthesis group (outside quotes); the API refuses that.

    Args:
        q (str): A boolean query.

    Returns:
        bool: Whether the query mixes them.
    """
    stack: list[set[str]] = [set()]
    for t in _TOKENS.findall(q):
        if t.startswith('"'):
            continue
        if t == "(":
            stack.append(set())
        elif t == ")":
            if len(stack) > 1:
                stack.pop()
        elif t in ("AND", "OR"):
            stack[-1].add(t)
            if {"AND", "OR"} <= stack[-1]:
                return True
    return False


def check_boolean_query(q: str) -> str:
    """Catch what the boolean endpoint refuses before a call is spent.

    Args:
        q (str): The query.

    Returns:
        str: The query, unchanged.

    Raises:
        ValueError: With the fix.
    """
    if _BAD_CHARS.search(q):
        raise ValueError(
            "Remove the characters [ ] / \\ : ^ from the query (field:value syntax is not supported; use search_in instead)."
        )
    if mixes_and_or(q):
        raise ValueError(
            "AND and OR can't be mixed at the same level: group with parentheses, e.g. "
            '("climate tech" AND fintech) OR "green fintech".'
        )
    return q


BooleanQuery = Annotated[str, Field(min_length=1), AfterValidator(check_boolean_query)]


def _top_sources_in(v: object) -> object:
    """``"top 200"`` → ``"top 200 global"``.

    Args:
        v (object): Raw input.

    Returns:
        object: Normalised input.
    """
    if isinstance(v, str):
        v = v.strip()
        if re.fullmatch(r"top\s+\d+", v, re.IGNORECASE):
            return f"{v} global"
    return v


def _top_sources_check(v: str) -> str:
    """Validate ``top <n> <country code|global>``.

    Args:
        v (str): Normalised input.

    Returns:
        str: The value.

    Raises:
        ValueError: With the expected format.
    """
    if not re.fullmatch(r"top \d{1,5} ([A-Za-z]{2}|global)", v, re.IGNORECASE):
        raise ValueError('Use "top <n> <country code>" or "top <n> global", e.g. "top 100 US".')
    return v


TopSources = Annotated[
    str | None,
    BeforeValidator(_top_sources_in),
    AfterValidator(lambda v: _top_sources_check(v) if v is not None else v),
    Field(description='Only the best-ranked publishers: "top <n> <country code>" or "top <n> global", e.g. "top 100 US" or "top 50 global".'),
]


class CompanyIn(BaseModel):
    """A company by website domain, with a name when the domain alone is ambiguous."""

    domain: Annotated[str, Field(min_length=3, description='Website domain, e.g. "wise.com".')]
    name: Annotated[str | None, Field(description="Name, when the domain alone is ambiguous.")] = None


CompanyItem = Annotated[str, Field(min_length=3, description='A company website domain, e.g. "stripe.com" (a URL works too).')] | CompanyIn


def to_company_in(items: list[str | CompanyIn]) -> list[dict[str, str]]:
    """Companies as the Agent API expects them.

    Args:
        items (list[str | CompanyIn]): Domains or objects.

    Returns:
        list[dict[str, str]]: ``[{"domain": ..., "name": ...}]``.
    """
    out: list[dict[str, str]] = []
    for c in items:
        if isinstance(c, str):
            out.append({"domain": c.strip()})
        else:
            out.append({"domain": c.domain.strip(), **({"name": c.name} if c.name else {})})
    return out


class Schedule(BaseModel):
    """When a monitor runs."""

    every: Annotated[
        Literal["day", "week", "hours"], Field(description="day (default), week, or hours (every N hours, Enterprise plans).")
    ] = "day"
    at: Annotated[str, Field(pattern=r"^\d{2}:\d{2}$", description="Local time HH:MM (default 09:00).")] = "09:00"
    tz: Annotated[str, Field(description='IANA timezone, e.g. "America/New_York" (default UTC).')] = "UTC"
    weekday: Annotated[int | None, Field(ge=0, le=6, description="Weekly only: 0 = Monday … 6 = Sunday.")] = None
    hours: Annotated[int | None, Field(ge=1, le=24, description="every=hours only: hours between runs.")] = None


def schedule_body(s: Schedule | None) -> dict[str, object] | None:
    """The schedule as the Agent API expects it; a weekly schedule without a weekday runs on Monday.

    Args:
        s (Schedule | None): The schedule.

    Returns:
        dict[str, object] | None: API body field.
    """
    if s is None:
        return None
    body = s.model_dump(exclude_none=True)
    if s.every == "week" and s.weekday is None:
        body["weekday"] = 0
    return body


_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def schedule_text(s: dict[str, object] | None) -> str:
    """A schedule in words.

    Args:
        s (dict[str, object] | None): Schedule from the API.

    Returns:
        str: e.g. ``"weekly on Wed at 09:00 UTC"``.
    """
    if not s:
        return ""
    if s.get("every") == "week":
        wd = s.get("weekday") or 0
        day = _DAYS[wd] if isinstance(wd, int) and 0 <= wd < 7 else wd
        return f"weekly on {day} at {s.get('at')} {s.get('tz')}"
    if s.get("every") == "hours":
        return f"every {s.get('hours')} h from {s.get('at')} {s.get('tz')}"
    return f"daily at {s.get('at')} {s.get('tz')}"


def drop_none(body: dict[str, object]) -> dict[str, object]:
    """Remove keys whose value is None.

    Args:
        body (dict[str, object]): A request body.

    Returns:
        dict[str, object]: The same dict without None values.
    """
    return {k: v for k, v in body.items() if v is not None}
