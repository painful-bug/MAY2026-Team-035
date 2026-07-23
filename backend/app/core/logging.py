"""Logging configuration.

A single :func:`configure_logging` call sets up a consistent format for the
whole process. Kept minimal on purpose — swap in structured/JSON logging here
later without touching call sites.
"""

from __future__ import annotations

import logging

from app.config import get_settings

_LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"


def configure_logging() -> None:
    """Initialise root logging based on the current environment."""
    level = logging.INFO if get_settings().is_production else logging.DEBUG
    logging.basicConfig(level=level, format=_LOG_FORMAT)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger."""
    return logging.getLogger(name)
