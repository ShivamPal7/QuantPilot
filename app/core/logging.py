"""Structured logging configuration for QuantPilot.

Ensures that API keys, secrets, and authorization headers are never logged.
"""

from __future__ import annotations

import logging
import re
import sys
from typing import Any

# Regex patterns for sensitive credentials
SENSITIVE_PATTERNS = [
    re.compile(r"(api[-_]?key)=['\"]?([a-zA-Z0-9_\-\.]{8,})['\"]?", re.IGNORECASE),
    re.compile(r"(api[-_]?secret)=['\"]?([a-zA-Z0-9_\-\.]{8,})['\"]?", re.IGNORECASE),
    re.compile(r"(signature)=['\"]?([a-fA-F0-9]{32,})['\"]?", re.IGNORECASE),
    re.compile(r"(secret)=['\"]?([a-zA-Z0-9_\-\.]{6,})['\"]?", re.IGNORECASE),
    re.compile(r"(authorization:\s*bearer\s+)([a-zA-Z0-9_\-\.]+)", re.IGNORECASE),
]


class SecretRedactingFormatter(logging.Formatter):
    """Log formatter that automatically masks API keys and secrets."""

    def format(self, record: logging.LogRecord) -> str:
        formatted = super().format(record)
        for pattern in SENSITIVE_PATTERNS:
            formatted = pattern.sub(r"\1=[REDACTED]", formatted)
        return formatted


def setup_logging(level: str = "INFO", json_format: bool = False) -> None:
    """Initialize structured console logging with secret masking."""
    log_level = getattr(logging, level.upper(), logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    if json_format:
        fmt = '{"timestamp":"%(asctime)s","level":"%(levelname)s","name":"%(name)s","message":"%(message)s"}'
    else:
        fmt = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"

    handler.setFormatter(SecretRedactingFormatter(fmt, datefmt="%Y-%m-%d %H:%M:%S"))

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    # Clear existing handlers to prevent duplicate lines
    root_logger.handlers.clear()
    root_logger.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """Return a module logger."""
    return logging.getLogger(name)
