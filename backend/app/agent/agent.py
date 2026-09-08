"""Agent construction.

Kept free of transport and persistence concerns so the same agent can be driven
by FastAPI, by the AgentCore runtime, or by a test (BUILD.md section 73).
"""

from __future__ import annotations

from typing import Any

import structlog
from strands import Agent

from app.agent.prompts import build_system_prompt
from app.agent.tools import ALL_TOOLS
from app.config import Settings, get_settings
from app.enums import MessageRole

logger = structlog.get_logger(__name__)


def to_strands_messages(history: list[tuple[MessageRole, str]]) -> list[dict[str, Any]]:
    """Convert stored conversation turns into Strands message dicts."""
    messages: list[dict[str, Any]] = []
    for role, content in history:
        if role is MessageRole.SYSTEM or not content.strip():
            continue
        messages.append(
            {"role": "user" if role is MessageRole.USER else "assistant", "content": [{"text": content}]}
        )
    return messages


def build_agent(
    *,
    history: list[tuple[MessageRole, str]] | None = None,
    settings: Settings | None = None,
    model: Any | None = None,
    system_prompt_extra: str | None = None,
) -> Agent:
    settings = settings or get_settings()
    if model is None:
        from app.agent.model import build_model

        model = build_model(settings)

    return Agent(
        model=model,
        tools=ALL_TOOLS,
        system_prompt=build_system_prompt(system_prompt_extra),
        messages=to_strands_messages(history or []),
        # Events are consumed through stream_async; the default stdout handler
        # would otherwise print the whole conversation to the server log.
        callback_handler=None,
    )
