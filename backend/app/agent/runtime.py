"""Running the agent for a session.

``run_agent`` is the plain callable the specification asks for (BUILD.md section
73) — FastAPI and the AgentCore entrypoint are both thin wrappers over it, so
none of the business logic is coupled to either transport.
"""

from __future__ import annotations

import uuid
from collections import deque
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.agent import build_agent
from app.agent.context import AgentContext, ToolEventView, agent_context
from app.db.models import Message, RecommendationRecord, Session, UserProfileRecord
from app.enums import MessageRole
from app.recommendation.models import RecommendationResult
from app.schemas.profile import UserProfile
from app.schemas.serializers import recommendation_to_dict

logger = structlog.get_logger(__name__)

MAX_HISTORY_TURNS = 40


@dataclass
class AgentResponse:
    session_id: uuid.UUID
    message: str
    profile: UserProfile
    recommendation: RecommendationResult | None = None
    tool_events: list[ToolEventView] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": str(self.session_id),
            "message": self.message,
            "profile": self.profile.model_dump(mode="json"),
            "recommendation": (
                recommendation_to_dict(self.recommendation) if self.recommendation else None
            ),
            "tool_events": [e.to_dict() for e in self.tool_events],
        }


async def get_or_create_session(db: AsyncSession, session_id: uuid.UUID | None) -> Session:
    if session_id is not None:
        existing = (
            await db.execute(select(Session).where(Session.id == session_id))
        ).scalar_one_or_none()
        if existing is not None:
            return existing
    session = Session(id=session_id or uuid.uuid4())
    db.add(session)
    await db.flush()
    return session


async def load_history(db: AsyncSession, session_id: uuid.UUID) -> list[tuple[MessageRole, str]]:
    rows = (
        (
            await db.execute(
                select(Message)
                .where(Message.session_id == session_id)
                .order_by(Message.created_at.desc())
                .limit(MAX_HISTORY_TURNS)
            )
        )
        .scalars()
        .all()
    )
    return [(row.role, row.content) for row in reversed(rows)]


async def load_profile(db: AsyncSession, session_id: uuid.UUID) -> UserProfile:
    record = (
        await db.execute(select(UserProfileRecord).where(UserProfileRecord.session_id == session_id))
    ).scalar_one_or_none()
    if record is None or not record.profile_json:
        return UserProfile()
    try:
        return UserProfile.model_validate(record.profile_json)
    except Exception:  # a shape change must not break an existing session
        logger.warning("profile.unreadable", session_id=str(session_id))
        return UserProfile()


async def save_profile(db: AsyncSession, session_id: uuid.UUID, profile: UserProfile) -> None:
    record = (
        await db.execute(select(UserProfileRecord).where(UserProfileRecord.session_id == session_id))
    ).scalar_one_or_none()
    payload = profile.model_dump(mode="json")
    if record is None:
        db.add(UserProfileRecord(session_id=session_id, profile_json=payload))
    else:
        record.profile_json = payload
    await db.flush()


async def save_message(db: AsyncSession, session_id: uuid.UUID, role: MessageRole, content: str) -> None:
    db.add(Message(session_id=session_id, role=role, content=content, created_at=datetime.now(UTC)))
    await db.flush()


async def save_recommendation(
    db: AsyncSession, session_id: uuid.UUID, result: RecommendationResult
) -> None:
    db.add(
        RecommendationRecord(
            session_id=session_id,
            recommended_card_id=result.recommended.card.id if result.recommended else None,
            recommendation_json=recommendation_to_dict(result),
            created_at=datetime.now(UTC),
        )
    )
    await db.flush()


async def _prepare(db: AsyncSession, session_id: uuid.UUID | None, message: str):
    session = await get_or_create_session(db, session_id)
    history = await load_history(db, session.id)
    profile = await load_profile(db, session.id)
    await save_message(db, session.id, MessageRole.USER, message)
    return session, history, profile


async def _finalise(
    db: AsyncSession, session_id: uuid.UUID, ctx: AgentContext, reply: str
) -> None:
    if reply.strip():
        await save_message(db, session_id, MessageRole.ASSISTANT, reply)
    if ctx.profile_dirty:
        await save_profile(db, session_id, ctx.profile)
    if ctx.recommendation is not None:
        await save_recommendation(db, session_id, ctx.recommendation)


async def run_agent(
    session_id: uuid.UUID | None,
    message: str,
    db: AsyncSession,
) -> AgentResponse:
    """Process one user message and return the complete reply."""
    session, history, profile = await _prepare(db, session_id, message)
    ctx = AgentContext(session_id=session.id, db=db, profile=profile)

    agent = build_agent(history=history)
    async with agent_context(ctx):
        result = await agent.invoke_async(message)

    reply = str(result)
    await _finalise(db, session.id, ctx, reply)

    return AgentResponse(
        session_id=session.id,
        message=reply,
        profile=ctx.profile,
        recommendation=ctx.recommendation,
        tool_events=ctx.events,
    )


async def stream_agent(
    session_id: uuid.UUID | None,
    message: str,
    db: AsyncSession,
) -> AsyncIterator[dict[str, Any]]:
    """Process one user message, yielding events as they happen.

    Tool events are emitted the moment each tool starts and finishes, so the
    activity feed reflects real work rather than a replay after the fact.
    """
    session, history, profile = await _prepare(db, session_id, message)

    pending: deque[ToolEventView] = deque()
    ctx = AgentContext(
        session_id=session.id, db=db, profile=profile, on_event=pending.append
    )

    yield {"type": "session", "session_id": str(session.id)}

    chunks: list[str] = []
    agent = build_agent(history=history)

    try:
        async with agent_context(ctx):
            async for event in agent.stream_async(message):
                while pending:
                    yield {"type": "tool_event", "event": pending.popleft().to_dict()}
                text = event.get("data") if isinstance(event, dict) else None
                if text:
                    chunks.append(text)
                    yield {"type": "text", "text": text}
    except Exception as exc:  # noqa: BLE001 — surface a controlled error
        logger.exception("agent.failed", session_id=str(session.id))
        while pending:
            yield {"type": "tool_event", "event": pending.popleft().to_dict()}
        yield {
            "type": "error",
            "error": {
                "code": "AGENT_FAILED",
                "message": "The assistant could not complete that request. Please try again.",
            },
        }
        logger.debug("agent.failure_detail", error=str(exc))
        return

    while pending:
        yield {"type": "tool_event", "event": pending.popleft().to_dict()}

    reply = "".join(chunks)
    await _finalise(db, session.id, ctx, reply)

    yield {"type": "profile", "profile": ctx.profile.model_dump(mode="json")}
    if ctx.recommendation is not None:
        yield {"type": "recommendation", "recommendation": recommendation_to_dict(ctx.recommendation)}
    yield {"type": "done", "message": reply}
