"""
Centralised logging configuration.

Call setup_logging() once at startup (before any other app code runs)
to configure the root logger and override uvicorn's default formatting.
"""

import logging

from app.config import settings

_FMT = "%(asctime)s %(levelname)-8s %(name)s — %(message)s"
_DATEFMT = "%Y-%m-%d %H:%M:%S"


def setup_logging() -> None:
    logging.basicConfig(
        level=settings.log_level.upper(),
        format=_FMT,
        datefmt=_DATEFMT,
    )

    # httpx logs every HTTP request at INFO — only show warnings+
    logging.getLogger("httpx").setLevel(logging.WARNING)

    # Uvicorn sets up its own handlers with a different format before our
    # code runs. Override their formatters so all log output is consistent.
    formatter = logging.Formatter(_FMT, datefmt=_DATEFMT)
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        for handler in logging.getLogger(name).handlers:
            handler.setFormatter(formatter)
