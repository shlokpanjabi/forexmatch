"""Structured logging (BUILD.md section 88).

Logs carry request and session identifiers, tool names and durations. They never
carry secrets, and the profile is summarised rather than dumped.
"""

from __future__ import annotations

import logging
import sys
import uuid
from contextvars import ContextVar

import structlog

request_id_var: ContextVar[str | None] = ContextVar("forexmatch_request_id", default=None)


def new_request_id() -> str:
    return uuid.uuid4().hex[:16]


def _inject_request_id(_logger, _name, event_dict):
    request_id = request_id_var.get()
    if request_id:
        event_dict.setdefault("request_id", request_id)
    return event_dict


def configure_logging(level: str = "INFO", *, json_output: bool = False) -> None:
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=getattr(logging, level.upper(), 20))

    renderer = (
        structlog.processors.JSONRenderer()
        if json_output
        else structlog.dev.ConsoleRenderer(colors=sys.stdout.isatty())
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            _inject_request_id,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, level.upper(), 20)),
        cache_logger_on_first_use=True,
    )
