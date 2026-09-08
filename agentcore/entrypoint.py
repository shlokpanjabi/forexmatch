"""Amazon Bedrock AgentCore Runtime entrypoint.

A thin adapter, nothing more. All the behaviour lives in ``app.agent.runtime``,
which exposes a plain ``run_agent(session_id, message, db)`` callable — so the
same agent runs under FastAPI, under AgentCore, or in a test, and none of the
business logic knows which (BUILD.md section 73).

Local:   agentcore dev      (or: python agentcore/entrypoint.py)
Deploy:  agentcore configure --entrypoint agentcore/entrypoint.py && agentcore launch
Invoke:  agentcore invoke '{"message": "I am going to the UK to study."}'
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

from bedrock_agentcore.runtime import BedrockAgentCoreApp  # noqa: E402

from app.agent.runtime import run_agent  # noqa: E402
from app.db.session import session_scope  # noqa: E402
from app.logging import configure_logging  # noqa: E402

configure_logging(json_output=True)

app = BedrockAgentCoreApp()


@app.entrypoint
async def invoke(payload: dict[str, Any]) -> dict[str, Any]:
    """Handle one turn.

    Payload:
        {"message": "...", "session_id": "<uuid, optional>"}

    The response mirrors POST /api/chat, so a client can move between the
    HTTP API and AgentCore without changing how it reads the result.
    """
    message = (payload or {}).get("message")
    if not message or not isinstance(message, str):
        return {
            "error": {
                "code": "INVALID_REQUEST",
                "message": "A 'message' string is required.",
            }
        }

    raw_session = (payload or {}).get("session_id")
    try:
        session_id = uuid.UUID(raw_session) if raw_session else None
    except (ValueError, AttributeError, TypeError):
        return {
            "error": {"code": "INVALID_REQUEST", "message": "'session_id' must be a UUID."}
        }

    async with session_scope() as db:
        response = await run_agent(session_id, message, db)

    return response.to_dict()


if __name__ == "__main__":
    app.run()
