"""Structured logging configuration using structlog."""

import logging
import sys
from contextvars import ContextVar
from typing import Any
from uuid import uuid4

import structlog

from app.config import get_settings

# Context variable for request correlation ID
request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)


def add_request_id(
    _logger: logging.Logger,
    _method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Add request ID to log entries if available."""
    request_id = request_id_ctx.get()
    if request_id:
        event_dict["request_id"] = request_id
    return event_dict


def configure_logging() -> None:
    """Configure structured logging for the application."""
    settings = get_settings()

    # Map string log level to logging constant
    log_level = getattr(logging, settings.log_level, logging.INFO)

    # Common processors for all environments
    shared_processors: list[structlog.typing.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        add_request_id,
    ]

    if settings.environment == "development":
        # Human-readable console output for development
        shared_processors.extend(
            [
                structlog.dev.ConsoleRenderer(colors=True),
            ]
        )
    else:
        # JSON output for production/staging (log aggregation friendly)
        shared_processors.extend(
            [
                structlog.processors.format_exc_info,
                structlog.processors.JSONRenderer(),
            ]
        )

    structlog.configure(
        processors=shared_processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure stdlib logging to use structlog
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    # Set log level for third-party libraries
    logging.getLogger("uvicorn").setLevel(log_level)
    logging.getLogger("uvicorn.access").setLevel(log_level)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured structlog logger
    """
    return structlog.get_logger(name)


def generate_request_id() -> str:
    """Generate a new request correlation ID."""
    return str(uuid4())[:8]
