"""Client-side analytics relay and the application click-through.

Routing the apply click through the backend means the click is tracked before
the user leaves, and it keeps affiliate-vs-official URL selection server-side
where ranking cannot see it (BUILD.md sections 52, 53).
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.analytics import ALLOWED_EVENTS
from app.api.deps import Analytics, DbSession
from app.db.models import Card
from app.errors import AppError, NotFoundError
from app.recommendation.service import to_card_facts

router = APIRouter(prefix="/api", tags=["analytics"])


class EventRequest(BaseModel):
    session_id: uuid.UUID
    event: str = Field(max_length=60)
    properties: dict[str, Any] = Field(default_factory=dict)


@router.post("/events")
async def record_event(request: EventRequest, analytics: Analytics) -> dict[str, Any]:
    if request.event not in ALLOWED_EVENTS:
        raise AppError(f"Unknown event '{request.event}'.", code="UNKNOWN_EVENT")
    analytics.capture(request.event, session_id=str(request.session_id), properties=request.properties)
    return {"recorded": True, "event": request.event}


class ApplicationClickRequest(BaseModel):
    session_id: uuid.UUID
    slug: str
    source: str = "recommendation"


@router.post("/application-click")
async def application_click(
    request: ApplicationClickRequest, db: DbSession, analytics: Analytics
) -> dict[str, Any]:
    """Record the click and return the URL to open."""
    row = (await db.execute(select(Card).where(Card.slug == request.slug))).scalar_one_or_none()
    if row is None:
        raise NotFoundError(f"No card with slug '{request.slug}'.")

    card = to_card_facts(row)
    analytics.capture(
        "application_click",
        session_id=str(request.session_id),
        properties={
            "card_id": str(card.id),
            "card_slug": card.slug,
            "provider": card.provider,
            "source": request.source,
        },
    )
    return {
        "application_url": card.apply_url,
        "is_affiliate": bool(card.affiliate_tracking_enabled and card.affiliate_url),
        "note": "ForexMatch does not process applications; this opens the provider's own flow.",
    }
