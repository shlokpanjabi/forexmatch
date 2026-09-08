"""Agent loop, tool wiring and persistence.

Driven by a scripted model so the whole path is exercised deterministically,
without depending on a provider being reachable.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.agent.agent import build_agent
from app.agent.context import AgentContext, agent_context
from app.agent.runtime import run_agent, stream_agent
from app.db.models import Message, RecommendationRecord, ToolEvent, UserProfileRecord
from app.enums import MessageRole, ToolStatus
from tests.scripted_model import ScriptedModel, ToolCall, Turn

UK_STUDENT = dict(
    destination_country="United Kingdom",
    destination_currency="GBP",
    trip_duration_months=24,
    monthly_spend_min=1000,
    monthly_spend_max=1200,
    monthly_spend_currency="GBP",
    atm_usage="low",
    student_status=True,
)

FULL_JOURNEY = [
    Turn(tool_calls=[ToolCall("update_user_profile", UK_STUDENT)]),
    Turn(tool_calls=[ToolCall("search_cards", {"destination_currency": "GBP"})]),
    Turn(tool_calls=[ToolCall("get_fx_rate", {"base_currency": "GBP", "quote_currency": "INR"})]),
    Turn(tool_calls=[ToolCall("compare_cards", {})]),
    Turn(text="Based on your usage, the Axis Multi-Currency Forex Card is your best match."),
]


async def _run(db_session, turns, message="I'm going to the UK to study.", session_id=None):
    model = ScriptedModel(turns)
    import app.agent.runtime as runtime

    original = runtime.build_agent
    runtime.build_agent = lambda **kwargs: build_agent(**{**kwargs, "model": model})
    try:
        response = await run_agent(session_id or uuid.uuid4(), message, db_session)
    finally:
        runtime.build_agent = original
    return response, model


async def test_agent_runs_the_full_research_sequence(db_session, static_fx):
    response, model = await _run(db_session, FULL_JOURNEY)

    assert model.calls_seen == [
        "update_user_profile",
        "search_cards",
        "get_fx_rate",
        "compare_cards",
    ]
    assert response.recommendation is not None
    assert response.recommendation.recommended is not None
    assert "Axis" in response.message


async def test_profile_is_extracted_and_persisted(db_session, static_fx):
    session_id = uuid.uuid4()
    response, _ = await _run(db_session, FULL_JOURNEY, session_id=session_id)

    profile = response.profile
    assert profile.destination_country == "United Kingdom"
    assert profile.destination_currencies == ["GBP"]
    assert profile.trip_duration_months == 24
    assert profile.monthly_spend.describe() == "GBP 1,000–1,200"
    assert profile.is_ready_for_recommendation

    stored = (
        await db_session.execute(
            select(UserProfileRecord).where(UserProfileRecord.session_id == session_id)
        )
    ).scalar_one()
    assert stored.profile_json["destination_country"] == "United Kingdom"


async def test_tool_events_are_recorded_for_real_calls(db_session, static_fx):
    session_id = uuid.uuid4()
    response, _ = await _run(db_session, FULL_JOURNEY, session_id=session_id)

    names = [e.tool_name for e in response.tool_events]
    assert names == ["update_user_profile", "search_cards", "get_fx_rate", "compare_cards"]
    assert all(e.status is ToolStatus.SUCCESS for e in response.tool_events)
    assert all(e.duration_ms is not None for e in response.tool_events)

    rows = (
        (await db_session.execute(select(ToolEvent).where(ToolEvent.session_id == session_id)))
        .scalars()
        .all()
    )
    assert len(rows) == 4, "every tool call must leave a row the activity feed can read"


async def test_messages_are_persisted_in_order(db_session, static_fx):
    session_id = uuid.uuid4()
    await _run(db_session, FULL_JOURNEY, session_id=session_id)

    rows = (
        (
            await db_session.execute(
                select(Message).where(Message.session_id == session_id).order_by(Message.created_at)
            )
        )
        .scalars()
        .all()
    )
    assert [r.role for r in rows] == [MessageRole.USER, MessageRole.ASSISTANT]


async def test_recommendation_is_persisted(db_session, static_fx):
    session_id = uuid.uuid4()
    await _run(db_session, FULL_JOURNEY, session_id=session_id)

    row = (
        await db_session.execute(
            select(RecommendationRecord).where(RecommendationRecord.session_id == session_id)
        )
    ).scalar_one()
    assert row.recommended_card_id is not None
    assert row.recommendation_json["recommended_card"]["match_score"] > 0
    assert "not financial advice" in row.recommendation_json["disclaimer"]


async def test_comparing_before_the_profile_is_ready_is_refused(db_session, static_fx):
    response, _ = await _run(
        db_session,
        [Turn(tool_calls=[ToolCall("compare_cards", {})]), Turn(text="I need a little more detail first.")],
    )
    assert response.recommendation is None
    event = response.tool_events[0]
    assert event.tool_name == "compare_cards"
    assert event.status is ToolStatus.SUCCESS  # returns a structured error, not a crash


async def test_tool_failure_is_reported_not_raised(db_session, static_fx):
    response, _ = await _run(
        db_session,
        [
            Turn(tool_calls=[ToolCall("get_card_details", {"slug": "no-such-card"})]),
            Turn(text="I could not find that card."),
        ],
    )
    assert "could not find" in response.message.lower()


async def test_re_ranking_updates_weights_and_reruns(db_session, static_fx):
    """BUILD.md section 82 — priorities change, ranking changes."""
    session_id = uuid.uuid4()
    await _run(db_session, FULL_JOURNEY, session_id=session_id)

    rerank = [
        Turn(
            tool_calls=[
                ToolCall(
                    "update_user_profile",
                    {"priority_rewards": 0.9, "priority_cost": 0.05, "priority_convenience": 0.05},
                )
            ]
        ),
        Turn(tool_calls=[ToolCall("compare_cards", {})]),
        Turn(text="Since rewards now matter most, the ranking changes."),
    ]
    response, _ = await _run(
        db_session, rerank, message="Actually I care about rewards, not fees.", session_id=session_id
    )

    assert response.profile.priorities_customised
    assert response.recommendation is not None
    weights = response.recommendation.weights_used
    assert weights["rewards"] > weights["cost"]
    assert sum(weights.values()) == pytest.approx(1.0, abs=1e-6)


async def test_streaming_emits_tool_events_then_result(db_session, static_fx):
    import app.agent.runtime as runtime

    model = ScriptedModel(FULL_JOURNEY)
    original = runtime.build_agent
    runtime.build_agent = lambda **kwargs: build_agent(**{**kwargs, "model": model})
    try:
        kinds = []
        async for event in stream_agent(uuid.uuid4(), "I'm off to the UK.", db_session):
            kinds.append(event["type"])
    finally:
        runtime.build_agent = original

    assert kinds[0] == "session"
    assert kinds[-1] == "done"
    assert "tool_event" in kinds
    assert "recommendation" in kinds


async def test_tools_refuse_to_run_outside_an_invocation():
    from app.agent.context import AgentContextError
    from app.agent.tools.profile import get_user_profile

    with pytest.raises(AgentContextError):
        await get_user_profile()


async def test_context_is_isolated_between_invocations(db_session):
    from app.agent.context import get_context

    ctx_a = AgentContext(session_id=uuid.uuid4(), db=db_session)
    async with agent_context(ctx_a):
        assert get_context() is ctx_a
        ctx_b = AgentContext(session_id=uuid.uuid4(), db=db_session)
        async with agent_context(ctx_b):
            assert get_context() is ctx_b
        assert get_context() is ctx_a
