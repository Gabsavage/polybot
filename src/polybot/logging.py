"""Structured logging via structlog."""

import logging
from pathlib import Path

import structlog


def setup_logging(level: str = "INFO", log_dir: Path | None = None) -> None:
    """Configure structlog with JSON file output + human-readable console."""
    if log_dir:
        log_dir.mkdir(parents=True, exist_ok=True)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer()
            if not log_dir
            else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
