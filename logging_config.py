"""Application logging configuration."""
from __future__ import annotations

import logging
import sys

from config import LOG_LEVEL


def setup_logging() -> None:
    """Configure application logging."""
    level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)
    format_str = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    date_fmt = "%Y-%m-%d %H:%M:%S"

    # Root logger
    root = logging.getLogger()
    root.setLevel(level)

    # Remove existing handlers
    for h in root.handlers[:]:
        root.removeHandler(h)

    # Console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(format_str, date_fmt))
    root.addHandler(handler)

    # Application logger
    app_log = logging.getLogger("google_employee")
    app_log.setLevel(level)

    # Reduce noise from third-party libs
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("google").setLevel(logging.WARNING)
    logging.getLogger("googleapiclient").setLevel(logging.WARNING)
