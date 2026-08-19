"""Credentials must never reach the logs.

Census takes its API key as a query parameter, and httpx logs the full
request URL at INFO. Left alone that writes a live key to stdout, which on
Railway means into the log store.
"""

from __future__ import annotations

import logging

from robotics_radar.logging import _URL_LOGGING_LIBRARIES, configure_logging


def test_url_logging_libraries_are_quietened():
    configure_logging("INFO")
    for name in _URL_LOGGING_LIBRARIES:
        assert logging.getLogger(name).level >= logging.WARNING, (
            f"{name} would log full request URLs, which can contain API keys"
        )


def test_still_quiet_when_app_log_level_is_debug():
    """A debug session must not silently start leaking keys."""
    configure_logging("DEBUG")
    for name in _URL_LOGGING_LIBRARIES:
        assert logging.getLogger(name).level >= logging.WARNING
