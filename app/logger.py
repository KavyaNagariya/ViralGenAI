"""
app/logger.py
─────────────────────────────────────────────
Configures a JSON-structured logger for the entire app.
Every log line includes: timestamp, level, module, message.
"""
import logging
import json
import sys
from datetime import datetime, timezone
from app.config import settings


class _JsonFormatter(logging.Formatter):
    """Emit each log record as a single-line JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "module": record.module,
            "funcName": record.funcName,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_obj)


def get_logger(name: str) -> logging.Logger:
    """
    Return a named logger configured with JSON output.
    Call once per module:  logger = get_logger(__name__)
    """
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(_JsonFormatter())
        logger.addHandler(handler)
        logger.propagate = False

    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logger.setLevel(level)

    return logger
