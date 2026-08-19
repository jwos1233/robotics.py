"""Structured JSON logging to stdout.

Railway captures stdout, so JSON lines here are queryable in the log viewer.
Fetchers log a structured event on failure rather than swallowing it.
"""

from __future__ import annotations

import logging
import sys

import structlog

#: Loggers that emit full request URLs at INFO. Several source APIs take their
#: credential as a query parameter -- Census is one -- so leaving these at INFO
#: writes live API keys into stdout, which on Railway means into the log store.
_URL_LOGGING_LIBRARIES = ("httpx", "httpcore", "urllib3")


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level.upper())

    for name in _URL_LOGGING_LIBRARIES:
        logging.getLogger(name).setLevel(logging.WARNING)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(level.upper())
        ),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str):
    return structlog.get_logger(name)
