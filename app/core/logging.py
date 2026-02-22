"""Structured logging setup using structlog.

Configures structlog to:
- Output JSON in production, pretty console in dev
- Bind context vars (tenant_id, run_id, request_id) to every log line
- Integrate with stdlib logging so existing loggers get structured output
"""

import logging
import sys
from contextvars import ContextVar

import structlog

from app.config import get_settings

# ── Context variables (bound per-request/per-task) ───────────────────

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
tenant_id_var: ContextVar[str | None] = ContextVar("tenant_id", default=None)
run_id_var: ContextVar[str | None] = ContextVar("run_id", default=None)
user_id_var: ContextVar[str | None] = ContextVar("user_id", default=None)


def _inject_context_vars(
    logger: logging.Logger,
    method_name: str,
    event_dict: dict,
) -> dict:
    """Structlog processor that injects context vars into every log entry."""
    for var, key in [
        (request_id_var, "request_id"),
        (tenant_id_var, "tenant_id"),
        (run_id_var, "run_id"),
        (user_id_var, "user_id"),
    ]:
        val = var.get(None)
        if val is not None:
            event_dict[key] = val
    return event_dict


def setup_logging() -> None:
    """Configure structlog + stdlib logging. Call once at app startup."""
    settings = get_settings()
    is_dev = settings.debug
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # Shared processors
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        _inject_context_vars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    renderer = structlog.dev.ConsoleRenderer() if is_dev else structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Configure stdlib root logger to use structlog formatter
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)

    # Reduce noise from third-party libs
    for noisy in ("httpx", "httpcore", "uvicorn.access", "sqlalchemy.engine"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Get a structlog logger instance."""
    return structlog.get_logger(name)
