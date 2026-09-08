"""HTTP surface: contracts, error shapes and the admin guard."""

from __future__ import annotations

import json
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.agent.agent import build_agent
from app.api.deps import db_dependency
from app.main import create_app
from tests.scripted_model import ScriptedModel, ToolCall, Turn

ADMIN_HEADERS = {"X-Admin-Secret": "test-admin-secret"}

JOURNEY = [
    Turn(
        tool_calls=[
            ToolCall(
                "update_user_profile",
                {
                    "destination_country": "United Kingdom",
                    "destination_currency": "GBP",
                    "trip_duration_months": 24,
                    "monthly_spend_min": 1000,
                    "monthly_spend_max": 1200,
                    "monthly_spend_currency": "GBP",
                    "atm_usage": "low",
                },
            )
        ]
    ),
    Turn(tool_calls=[ToolCall("compare_cards", {})]),
    Turn(text="The Axis Multi-Currency Forex Card looks like your best match."),
]


@pytest_asyncio.fixture
async def client(db_session, static_fx, monkeypatch):
    app = create_app()

    async def override_db():
        yield db_session

    app.dependency_overrides[db_dependency] = override_db

    import app.agent.runtime as runtime

    monkeypatch.setattr(
        runtime, "build_agent", lambda **kw: build_agent(**{**kw, "model": ScriptedModel(JOURNEY)})
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def test_health_and_root(client):
    health = await client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    root = await client.get("/")
    assert "not financial advice" in root.json()["disclaimer"]


async def test_list_and_fetch_cards(client):
    listing = await client.get("/api/cards")
    assert listing.status_code == 200
    body = listing.json()
    assert body["count"] >= 10

    slug = body["cards"][0]["slug"]
    detail = await client.get(f"/api/cards/{slug}")
    assert detail.status_code == 200
    assert "fees" in detail.json()
    assert "sources" in detail.json()


async def test_filtering_cards_by_currency(client):
    response = await client.get("/api/cards", params={"currency": "GBP"})
    assert response.status_code == 200
    for card in response.json()["cards"]:
        assert "GBP" in card["supported_currencies"]


async def test_unknown_card_returns_structured_error(client):
    response = await client.get("/api/cards/not-a-real-card")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


async def test_chat_returns_profile_recommendation_and_tool_events(client):
    response = await client.post("/api/chat", json={"message": "I'm going to the UK for a master's."})
    assert response.status_code == 200
    body = response.json()

    assert body["session_id"]
    assert body["profile"]["destination_country"] == "United Kingdom"
    assert body["recommendation"]["recommended_card"]["match_score"] > 0
    assert [e["tool_name"] for e in body["tool_events"]] == ["update_user_profile", "compare_cards"]
    assert "not financial advice" in body["recommendation"]["disclaimer"]


async def test_chat_rejects_an_empty_message(client):
    response = await client.post("/api/chat", json={"message": ""})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


async def test_chat_stream_emits_server_sent_events(client):
    async with client.stream(
        "POST", "/api/chat/stream", json={"message": "I'm off to the UK."}
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        kinds = []
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                kinds.append(json.loads(line[6:])["type"])

    assert kinds[0] == "session"
    assert "tool_event" in kinds
    assert kinds[-1] == "done"


async def test_session_can_be_rehydrated(client):
    created = await client.post("/api/chat", json={"message": "UK, two years."})
    session_id = created.json()["session_id"]

    response = await client.get(f"/api/sessions/{session_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["exists"] is True
    assert len(body["messages"]) == 2
    assert body["recommendation"] is not None


async def test_unknown_session_is_reported_not_errored(client):
    response = await client.get(f"/api/sessions/{uuid.uuid4()}")
    assert response.status_code == 200
    assert response.json()["exists"] is False


async def test_recommendation_endpoint_reranks_directly(client):
    payload = {
        "profile": {
            "destination_currencies": ["GBP"],
            "trip_duration_months": 24,
            "monthly_spend": {"min_amount": "1000", "max_amount": "1200", "currency": "GBP"},
            "atm_usage": "high",
            "priorities": {"cost": 0.2, "atm": 0.8, "currency_support": 0.0,
                           "convenience": 0.0, "rewards": 0.0, "security": 0.0},
            "priorities_customised": True,
        }
    }
    response = await client.post("/api/recommendations", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["recommended_card"] is not None
    assert body["weights_used"]["atm"] > body["weights_used"]["cost"]
    assert body["weights_were_customised"] is True


async def test_recommendation_requires_a_usable_profile(client):
    response = await client.post("/api/recommendations", json={"profile": {}})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "PROFILE_INCOMPLETE"


async def test_application_click_is_tracked_and_returns_the_url(client):
    listing = await client.get("/api/cards")
    slug = next(c["slug"] for c in listing.json()["cards"] if c["slug"] != "hdfc-forexplus-corporate")

    response = await client.post(
        "/api/application-click", json={"session_id": str(uuid.uuid4()), "slug": slug}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["application_url"]
    assert body["is_affiliate"] is False
    assert "does not process applications" in body["note"]


async def test_unknown_analytics_event_is_rejected(client):
    response = await client.post(
        "/api/events", json={"session_id": str(uuid.uuid4()), "event": "steal_all_the_data"}
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "UNKNOWN_EVENT"


async def test_admin_requires_the_secret(client):
    unauthorised = await client.get("/admin/cards")
    assert unauthorised.status_code == 401
    assert unauthorised.json()["error"]["code"] == "UNAUTHORIZED"

    wrong = await client.get("/admin/cards", headers={"X-Admin-Secret": "nope"})
    assert wrong.status_code == 401

    ok = await client.get("/admin/cards", headers=ADMIN_HEADERS)
    assert ok.status_code == 200
    assert ok.json()["count"] >= 10


async def test_admin_lists_stale_cards_and_changes(client):
    stale = await client.get("/admin/stale-cards", headers=ADMIN_HEADERS)
    assert stale.status_code == 200

    changes = await client.get("/admin/verification/changes", headers=ADMIN_HEADERS)
    assert changes.status_code == 200
    assert "changes" in changes.json()


async def test_verification_never_writes_to_the_catalogue(client):
    """Research is unavailable in tests, so the run must complete having changed nothing."""
    listing = await client.get("/admin/cards", headers=ADMIN_HEADERS)
    card_id = listing.json()["cards"][0]["id"]

    before = await client.get(f"/admin/cards/{card_id}", headers=ADMIN_HEADERS)
    run = await client.post(f"/admin/cards/{card_id}/verify", headers=ADMIN_HEADERS)
    assert run.status_code == 200
    assert run.json()["status"] == "completed"
    assert "nothing has been written" in run.json()["note"]

    after = await client.get(f"/admin/cards/{card_id}", headers=ADMIN_HEADERS)
    assert before.json()["fees"] == after.json()["fees"]


async def test_every_specified_analytics_event_is_reachable():
    """BUILD.md section 54 names nine events; none should be dead code."""
    from app.analytics import ALLOWED_EVENTS

    specified = {
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
    assert specified <= ALLOWED_EVENTS


async def test_a_first_ranking_is_generated_and_a_second_is_recalculated(client, monkeypatch):
    """The same session ranking twice is a re-rank, not a fresh result."""
    captured: list[tuple[str, dict]] = []

    from app.analytics.client import AnalyticsClient

    monkeypatch.setattr(
        AnalyticsClient,
        "capture",
        lambda self, event, *, session_id, properties=None: captured.append((event, properties or {})),
    )

    first = await client.post("/api/chat", json={"message": "UK, two years, about £1,100 a month."})
    session_id = first.json()["session_id"]
    events = [name for name, _ in captured]
    assert "session_started" in events
    assert "profile_completed" in events
    assert "recommendation_generated" in events
    assert "recommendation_recalculated" not in events

    captured.clear()
    await client.post(
        "/api/chat", json={"session_id": session_id, "message": "Actually I'll use more cash."}
    )
    events = [name for name, _ in captured]
    assert "recommendation_recalculated" in events
    assert "recommendation_generated" not in events
    # profile_completed fires once, not on every subsequent turn.
    assert "profile_completed" not in events


async def test_analytics_never_carries_spend_or_identifiers(client, monkeypatch):
    captured: list[dict] = []

    from app.analytics.client import ALLOWED_PROPERTIES, AnalyticsClient

    original = AnalyticsClient.capture

    def spy(self, event, *, session_id, properties=None):
        captured.append(properties or {})
        return original(self, event, session_id=session_id, properties=properties)

    monkeypatch.setattr(AnalyticsClient, "capture", spy)
    await client.post("/api/chat", json={"message": "UK, two years, about £1,100 a month."})

    for properties in captured:
        for key in properties:
            assert key in ALLOWED_PROPERTIES, f"unexpected analytics property: {key}"
        assert not any("spend" in k or "amount" in k for k in properties)
