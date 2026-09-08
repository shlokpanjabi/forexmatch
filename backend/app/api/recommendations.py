"""Direct recommendation endpoint.

Lets a client re-rank without a conversation — the "actually, I'll withdraw cash
twice a week" case (BUILD.md section 34) — by posting an updated profile.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.deps import Analytics, DbSession
from app.errors import ProfileIncompleteError, RecommendationFailedError
from app.recommendation.service import RecommendationService
from app.schemas.profile import UserProfile
from app.schemas.serializers import recommendation_to_dict

router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])


class RecommendationRequest(BaseModel):
    session_id: uuid.UUID | None = None
    profile: UserProfile
    max_results: int = 3


@router.post("")
async def create_recommendation(
    request: RecommendationRequest, db: DbSession, analytics: Analytics
) -> dict[str, Any]:
    profile = request.profile
    if not profile.is_ready_for_recommendation:
        raise ProfileIncompleteError(
            "A destination currency and an approximate monthly spend are needed before "
            "cards can be compared."
        )

    session_id = str(request.session_id or uuid.uuid4())
    analytics.capture("recommendation_started", session_id=session_id)

    try:
        result = await RecommendationService(db).recommend_for_profile(
            profile, max_results=max(1, min(request.max_results, 10))
        )
    except Exception as exc:  # noqa: BLE001
        # A failed ranking returns a controlled error; it never falls back to a
        # model-invented recommendation (BUILD.md section 65).
        raise RecommendationFailedError(
            "The comparison could not be completed. Please try again."
        ) from exc

    if result.recommended:
        analytics.capture(
            "recommendation_generated",
            session_id=session_id,
            properties={
                "top_card_id": str(result.recommended.card.id),
                "destination_country": profile.destination_country,
                "confidence": result.confidence.value,
                "cards_compared": len(result.comparison),
            },
        )
    return recommendation_to_dict(result)
