"""Structured JSON logging (Stackdriver-style JSON lines).

No logging dependency beyond the standard library. Each record is one JSON
line with ``severity``, ``asctime``, ``message``, ``name`` and every key passed in ``extra={...}``. The level comes
from the ``LOG_LEVEL`` env var (default INFO).

Never log an API key, a query or any other user content: these logs ship to a Vercel log drain.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

# Attributes every LogRecord has; anything else on a record came from ``extra={...}``.
_RESERVED = set(vars(logging.LogRecord("", 0, "", 0, "", None, None))) | {"message", "asctime", "taskName"}


class StackdriverFormatter(logging.Formatter):
    """Formats a record as one JSON object (Stackdriver style: ``severity`` instead of ``levelname``)."""

    def format(self, record: logging.LogRecord) -> str:
        """Render the record as a JSON line.

        Args:
            record (logging.LogRecord): The record to render.

        Returns:
            str: One JSON object.
        """
        out: dict[str, Any] = {
            "severity": record.levelname,
            "asctime": self.formatTime(record),
            "message": record.getMessage(),
            "name": record.name,
        }
        for key, value in vars(record).items():
            if key not in _RESERVED and not key.startswith("_"):
                out[key] = value
        if record.exc_info:
            out["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(out, default=str, ensure_ascii=False)


def setup_logging(name: str) -> logging.Logger:
    """Return a logger that writes JSON lines to stderr.

    Args:
        name (str): Logger name, normally ``__name__``.

    Returns:
        logging.Logger: The configured logger.
    """
    level = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)
    logger = logging.getLogger(name)
    logger.propagate = False
    logger.setLevel(level)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setLevel(level)
        handler.setFormatter(StackdriverFormatter())
        logger.addHandler(handler)
    return logger
