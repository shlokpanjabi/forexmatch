"""Analytics behind an interface (BUILD.md sections 54, 86).

PostHog is optional. With no key configured every call is a no-op and the
application behaves identically — analytics is never load-bearing.

Only the events named in the specification are sent, and only with
non-identifying properties. Spend figures, destinations tied to a person, and
anything resembling personal or financial data stay out.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import structlog

from app.config import Settings, get_settings

logger = structlog.get_logger(__name__)

ALLOWED_EVENTS = {
    "session_started",
    "message_sent",
    "profile_completed",
    "recommendation_started",
    "recommendation_generated",
    "card_viewed",
    "alternative_viewed",
    "application_click",
    "recommendation_recalculated",
}

#: Properties we are willing to record. Anything else is dropped.
ALLOWED_PROPERTIES = {
    "destination_country",
    "destination_currency",
    "top_card_id",
    "card_id",
    "card_slug",
    "provider",
    "source",
    "confidence",
    "cards_compared",
    "duration_months",
    "trip_type",
    "student_status",
}


class AnalyticsClient:
    """Fire-and-forget event capture."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._client: Any | None = None
        if not self._settings.analytics_enabled:
            logger.info("analytics.disabled")
            return
        try:
            from posthog import Posthog

            self._client = Posthog(
                project_api_key=self._settings.posthog_api_key,
                host=self._settings.posthog_host,
            )
            logger.info("analytics.enabled", host=self._settings.posthog_host)
        except Exception as exc:  # noqa: BLE001 — analytics must never break a request
            logger.warning("analytics.init_failed", error=str(exc))
            self._client = None

    @property
    def enabled(self) -> bool:
        return self._client is not None

    def capture(self, event: str, *, session_id: str, properties: dict[str, Any] | None = None) -> None:
        if event not in ALLOWED_EVENTS:
            logger.warning("analytics.event_rejected", event_name=event)
            return
        safe = {k: v for k, v in (properties or {}).items() if k in ALLOWED_PROPERTIES}
        if self._client is None:
            logger.debug("analytics.noop", event_name=event, properties=safe)
            return
        try:
            self._client.capture(distinct_id=session_id, event=event, properties=safe)
        except Exception as exc:  # noqa: BLE001
            logger.warning("analytics.capture_failed", event_name=event, error=str(exc))

    def shutdown(self) -> None:
        if self._client is not None:
            try:
                self._client.shutdown()
            except Exception:  # noqa: BLE001
                pass


@lru_cache(maxsize=1)
def get_analytics() -> AnalyticsClient:
    return AnalyticsClient()
