"""Per-invocation context for agent tools.

Strands tools are plain functions, so they need some way to reach the current
database session, the session id and the evolving profile. A ContextVar carries
that per-invocation state without turning it into global mutable state: each
agent run binds its own context, and concurrent runs never see each other's.

Tool invocations are recorded here as they happen. The UI's activity feed reads
these rows, so it always reflects work the agent actually did (BUILD.md sections
48, 50, 89) — there is no code path that writes a tool event the agent did not
trigger.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import wraps
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ToolEvent
from app.enums import ToolStatus
from app.recommendation.models import RecommendationResult
from app.schemas.profile import UserProfile

logger = structlog.get_logger(__name__)

MAX_SUMMARY_CHARS = 400


@dataclass
class ToolEventView:
    """In-memory mirror of a tool_events row, streamed to the client."""

    id: uuid.UUID
    tool_name: str
    status: ToolStatus
    input_summary: str | None = None
    output_summary: str | None = None
    error_message: str | None = None
    duration_ms: int | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "tool_name": self.tool_name,
            "status": self.status.value,
            "input_summary": self.input_summary,
            "output_summary": self.output_summary,
            "error_message": self.error_message,
            "duration_ms": self.duration_ms,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


@dataclass
class AgentContext:
    """State shared by every tool within a single agent invocation."""

    session_id: uuid.UUID
    db: AsyncSession
    profile: UserProfile = field(default_factory=UserProfile)
    recommendation: RecommendationResult | None = None
    events: list[ToolEventView] = field(default_factory=list)
    #: Called as each event starts and completes, so the API can stream them.
    on_event: Callable[[ToolEventView], None] | None = None
    profile_dirty: bool = False

    #: Strands runs the tools requested in a single turn concurrently, and an
    #: AsyncSession is not safe for concurrent use — interleaved flushes lose
    #: the identity of pending rows, so a tool event gets INSERTed twice and the
    #: first copy is stranded at "started". Serialising tool bodies keeps every
    #: database touch on one task at a time. The tools are millisecond-scale, so
    #: the lost parallelism is not worth the corruption it causes.
    db_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def emit(self, event: ToolEventView) -> None:
        if self.on_event is not None:
            self.on_event(event)


_context: ContextVar[AgentContext | None] = ContextVar("forexmatch_agent_context", default=None)


class AgentContextError(RuntimeError):
    """Raised when a tool runs outside an agent invocation."""


def get_context() -> AgentContext:
    ctx = _context.get()
    if ctx is None:
        raise AgentContextError("agent tool called outside of an agent invocation")
    return ctx


@asynccontextmanager
async def agent_context(ctx: AgentContext) -> AsyncIterator[AgentContext]:
    token = _context.set(ctx)
    try:
        yield ctx
    finally:
        _context.reset(token)


def _truncate(value: str | None) -> str | None:
    if value is None:
        return None
    value = " ".join(value.split())
    return value if len(value) <= MAX_SUMMARY_CHARS else value[: MAX_SUMMARY_CHARS - 1] + "…"


def traced_tool(
    describe_input: Callable[..., str] | None = None,
    describe_output: Callable[[Any], str] | None = None,
):
    """Record a tool call as a real, timed event.

    Errors are caught and returned to the model as structured failures rather
    than raised: a tool that cannot answer should let the agent say so, not
    abort the conversation (BUILD.md section 37).
    """

    def decorator(func):
        tool_name = func.__name__

        @wraps(func)
        async def wrapper(*args, **kwargs):
            ctx = get_context()
            # Held across the tool body too, not just the event writes: the tool
            # itself queries through the same session.
            async with ctx.db_lock:
                return await _run_traced(ctx, func, tool_name, args, kwargs)

        async def _run_traced(ctx, func, tool_name, args, kwargs):
            started = datetime.now(UTC)
            clock = time.perf_counter()

            try:
                input_summary = _truncate(describe_input(*args, **kwargs)) if describe_input else None
            except Exception:  # a summary must never break the call
                input_summary = None

            event = ToolEventView(
                id=uuid.uuid4(),
                tool_name=tool_name,
                status=ToolStatus.STARTED,
                input_summary=input_summary,
                started_at=started,
            )
            ctx.events.append(event)
            ctx.emit(event)

            record = ToolEvent(
                id=event.id,
                session_id=ctx.session_id,
                tool_name=tool_name,
                status=ToolStatus.STARTED,
                input_summary=input_summary,
                started_at=started,
            )
            ctx.db.add(record)
            await ctx.db.flush()

            try:
                result = await func(*args, **kwargs)
            except Exception as exc:
                duration = int((time.perf_counter() - clock) * 1000)
                message = f"{type(exc).__name__}: {exc}"
                logger.warning("tool.failed", tool=tool_name, error=message, duration_ms=duration)
                event.status = ToolStatus.ERROR
                event.error_message = _truncate(message)
                event.duration_ms = duration
                event.completed_at = datetime.now(UTC)
                record.status = ToolStatus.ERROR
                record.error_message = event.error_message
                record.duration_ms = duration
                record.completed_at = event.completed_at
                await ctx.db.flush()
                ctx.emit(event)
                return {"error": {"code": "TOOL_FAILED", "message": str(exc), "tool": tool_name}}

            duration = int((time.perf_counter() - clock) * 1000)
            try:
                output_summary = _truncate(describe_output(result)) if describe_output else None
            except Exception:
                output_summary = None

            logger.info("tool.completed", tool=tool_name, duration_ms=duration)
            event.status = ToolStatus.SUCCESS
            event.output_summary = output_summary
            event.duration_ms = duration
            event.completed_at = datetime.now(UTC)
            record.status = ToolStatus.SUCCESS
            record.output_summary = output_summary
            record.duration_ms = duration
            record.completed_at = event.completed_at
            await ctx.db.flush()
            ctx.emit(event)
            return result

        return wrapper

    return decorator
