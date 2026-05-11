"""
logger.py
---------
Centralised logging factory for the hw-validation-suite.
Provides rotating file logs + console output + optional JSON format.
Covers: debug automation failures, distinguish framework vs hardware defects.
"""

import logging
import logging.handlers
import json
import os
from datetime import datetime


LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "logs")
os.makedirs(LOG_DIR, exist_ok=True)

LOG_FILE = os.path.join(LOG_DIR, "hw_validation.log")
LOG_LEVEL = logging.DEBUG


class JSONFormatter(logging.Formatter):
    """Emit log records as single-line JSON for machine-readable ingestion."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.utcfromtimestamp(record.created).isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "line": record.lineno,
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def get_logger(name: str, use_json: bool = False) -> logging.Logger:
    """
    Return a named logger with:
      - RotatingFileHandler  → logs/hw_validation.log (5 MB × 3 backups)
      - StreamHandler        → console (WARNING+ to avoid noise during pytest)
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger   # already configured in this process

    logger.setLevel(LOG_LEVEL)

    # -- Rotating file handler --
    file_formatter = (
        JSONFormatter()
        if use_json
        else logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    )
    file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_formatter)

    # -- Console handler --
    console_formatter = logging.Formatter(
        fmt="%(levelname)-8s %(name)s — %(message)s"
    )
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(console_formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    logger.propagate = False

    return logger
