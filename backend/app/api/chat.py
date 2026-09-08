"""Chat endpoints (BUILD.md sections 45, 72)."""

from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.agent.runtime import run_agent, stream_agent
from app.api.deps import Analytics, DbSession
from app.db.models import Message, Session, ToolEvent
from app.enums import MessageRole
from app.schemas.serializers import recommendation_to_dict

router = APIRouter(prefix="/api", tags=["chat"])


class ChatRequest(BaseModel):
    session_id: uuid.UUID | None = None
    message: str = Field(min_length=1, max_length=4000)


class ChatResponse(BaseModel):
    session_id: str
    message: str
    profile: dict[str, Any]
    recommendation: dict[str, Any] | None
    tool_events: list[dict[str, Any]]


async def _prior_recommendation_count(db, session_id: uuid.UUID) -> int:
    from sqlalchemy import func

    from app.db.models import RecommendationRecord

    return (
        await db.execute(
            select(func.count())
            .select_from(RecommendationRecord)
            .where(RecommendationRecord.session_id == session_id)
        )
    ).scalar_one()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, db: DbSession, analytics: Analytics) -> ChatResponse:
    """Send a message and get the complete reply."""
    is_new = request.session_id is None
    had_recommendation = (
        False if is_new else await _prior_recommendation_count(db, request.session_id) > 0
    )
    profile_was_ready = False
    if not is_new:
        from app.agent.runtime import load_profile

        profile_was_ready = (await load_profile(db, request.session_id)).is_ready_for_recommendation

    response = await run_agent(request.session_id, request.message, db)

    session_id = str(response.session_id)
    if is_new:
        analytics.capture("session_started", session_id=session_id)
    analytics.capture("message_sent", session_id=session_id)

    # Fires once, on the turn where enough was learned to compare cards.
    if response.profile.is_ready_for_recommendation and not profile_was_ready:
        analytics.capture(
            "profile_completed",
            session_id=session_id,
            properties={
                "destination_country": response.profile.destination_country,
                "duration_months": response.profile.trip_duration_months,
                "student_status": response.profile.student_status,
            },
        )

    if response.recommendation and response.recommendation.recommended:
        analytics.capture(
            # A second ranking in the same session is a re-rank, not a first result.
            "recommendation_recalculated" if had_recommendation else "recommendation_generated",
            session_id=session_id,
            properties={
                "top_card_id": str(response.recommendation.recommended.card.id),
                "destination_country": response.profile.destination_country,
                "confidence": response.recommendation.confidence.value,
                "cards_compared": len(response.recommendation.comparison),
            },
        )

    return ChatResponse(**response.to_dict())


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest, db: DbSession, analytics: Analytics) -> StreamingResponse:
    """Server-sent events: tool activity as it happens, then text, then the result."""
    is_new = request.session_id is None

    async def events():
        try:
            async for event in stream_agent(request.session_id, request.message, db):
                if event["type"] == "session":
                    if is_new:
                        analytics.capture("session_started", session_id=event["session_id"])
                    analytics.capture("message_sent", session_id=event["session_id"])
                yield f"data: {json.dumps(event)}\n\n"
        except Exception:  # noqa: BLE001 — the stream must always close cleanly
            payload = {
                "type": "error",
                "error": {"code": "STREAM_FAILED", "message": "The response was interrupted."},
            }
            yield f"data: {json.dumps(payload)}\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


@router.get("/sessions/{session_id}")
async def get_session(session_id: uuid.UUID, db: DbSession) -> dict[str, Any]:
    """Rehydrate a conversation: messages, tool activity and the latest result."""
    from app.agent.runtime import load_profile
    from app.db.models import RecommendationRecord

    session = (await db.execute(select(Session).where(Session.id == session_id))).scalar_one_or_none()
    if session is None:
        return {"session_id": str(session_id), "exists": False, "messages": [], "tool_events": []}

    messages = (
        (await db.execute(select(Message).where(Message.session_id == session_id).order_by(Message.created_at)))
        .scalars()
        .all()
    )
    events = (
        (
            await db.execute(
                select(ToolEvent).where(ToolEvent.session_id == session_id).order_by(ToolEvent.started_at)
            )
        )
        .scalars()
        .all()
    )
    latest = (
        await db.execute(
            select(RecommendationRecord)
            .where(RecommendationRecord.session_id == session_id)
            .order_by(RecommendationRecord.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    profile = await load_profile(db, session_id)

    return {
        "session_id": str(session_id),
        "exists": True,
        "messages": [
            {"role": m.role.value, "content": m.content, "created_at": m.created_at.isoformat()}
            for m in messages
            if m.role is not MessageRole.SYSTEM
        ],
        "tool_events": [
            {
                "tool_name": e.tool_name,
                "status": e.status.value,
                "input_summary": e.input_summary,
                "output_summary": e.output_summary,
                "duration_ms": e.duration_ms,
                "started_at": e.started_at.isoformat(),
            }
            for e in events
        ],
        "profile": profile.model_dump(mode="json"),
        "recommendation": latest.recommendation_json if latest else None,
    }
