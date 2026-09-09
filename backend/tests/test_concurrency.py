"""Reproduce: concurrent tool calls sharing one AsyncSession corrupt tool_events."""
from __future__ import annotations

import uuid

from sqlalchemy import select

from app.agent.agent import build_agent
from app.agent.runtime import run_agent
from app.db.models import ToolEvent
from app.enums import ToolStatus
from tests.scripted_model import ScriptedModel, ToolCall, Turn


async def test_parallel_tool_calls_produce_one_event_each(db_session, static_fx):
    """The model may request several tools in one turn; Strands runs them
    concurrently. Each call must leave exactly one row, ending in a terminal
    status — the activity feed renders these directly."""
    slugs = [
        "axis-multi-currency-forex-card",
        "bookmyforex-multi-currency-forex-card",
        "icici-sapphiro-forex-prepaid-card",
        "thomas-cook-one-currency-card",
        "wsfx-globalpay-smart-currency-card",
    ]
    turns = [
        Turn(tool_calls=[ToolCall("get_card_details", {"slug": s}) for s in slugs]),
        Turn(text="Compared them."),
    ]

    model = ScriptedModel(turns)
    import app.agent.runtime as runtime

    original = runtime.build_agent
    runtime.build_agent = lambda **kw: build_agent(**{**kw, "model": model})
    session_id = uuid.uuid4()
    try:
        response = await run_agent(session_id, "Tell me about these.", db_session)
    finally:
        runtime.build_agent = original

    rows = (
        (await db_session.execute(select(ToolEvent).where(ToolEvent.session_id == session_id)))
        .scalars().all()
    )
    orphaned = [r for r in rows if r.status is ToolStatus.STARTED]

    assert len(rows) == len(slugs), f"expected {len(slugs)} rows, got {len(rows)}"
    assert not orphaned, f"{len(orphaned)} events stuck at 'started'"
    assert len(response.tool_events) == len(slugs)
    assert all(e.duration_ms is not None for e in response.tool_events)
