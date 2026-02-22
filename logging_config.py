"""Application logging configuration."""
from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path

from config import LOG_FILE, LOG_FILE_BACKUP_COUNT, LOG_FILE_MAX_BYTES, LOG_LEVEL


def setup_logging() -> None:
    """Configure application logging. Logs to stdout and optionally to a file."""
    level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)
    format_str = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    date_fmt = "%Y-%m-%d %H:%M:%S"
    formatter = logging.Formatter(format_str, date_fmt)

    # Root logger
    root = logging.getLogger()
    root.setLevel(level)

    # Remove existing handlers
    for h in root.handlers[:]:
        root.removeHandler(h)

    # Console handler (stdout)
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(formatter)
    root.addHandler(console)

    # File handler (optional)
    if LOG_FILE:
        try:
            log_path = Path(LOG_FILE).resolve()
            log_path.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.handlers.RotatingFileHandler(
                log_path,
                maxBytes=LOG_FILE_MAX_BYTES,
                backupCount=LOG_FILE_BACKUP_COUNT,
                encoding="utf-8",
            )
            file_handler.setLevel(level)
            file_handler.setFormatter(formatter)
            root.addHandler(file_handler)
        except Exception as e:
            logging.getLogger("google_employee").warning(
                "Could not add log file %s: %s", LOG_FILE, e
            )

    # Application logger
    app_log = logging.getLogger("google_employee")
    app_log.setLevel(level)

    # Reduce noise from third-party libs
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("google").setLevel(logging.WARNING)
    logging.getLogger("googleapiclient").setLevel(logging.WARNING)
    # Suppress googleapiclient's generic 403 log; we log full details in _log_http_error
    logging.getLogger("googleapiclient.http").setLevel(logging.ERROR)
