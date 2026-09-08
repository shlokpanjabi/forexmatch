"""A Strands model that follows a script instead of calling a provider.

Lets the whole agent loop — tool dispatch, the context var, tool-event tracing,
persistence and streaming — be tested deterministically and offline. The model's
*judgement* obviously is not tested; everything the model drives is.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterable
from dataclasses import dataclass
from typing import Any

from strands.models.model import Model


@dataclass
class ToolCall:
    name: str
    arguments: dict[str, Any]


@dataclass
class Turn:
    """One model response: either tool calls, or final text."""

    text: str | None = None
    tool_calls: list[ToolCall] | None = None


class ScriptedModel(Model):
    def __init__(self, turns: list[Turn]) -> None:
        self._turns = list(turns)
        self._index = 0
        self._config: dict[str, Any] = {"model_id": "scripted"}
        self.calls_seen: list[str] = []

    def update_config(self, **model_config: Any) -> None:
        self._config.update(model_config)

    def get_config(self) -> Any:
        return self._config

    async def stream(self, messages, tool_specs=None, system_prompt=None, **kwargs) -> AsyncIterable[Any]:
        turn = self._turns[self._index] if self._index < len(self._turns) else Turn(text="Done.")
        self._index += 1

        yield {"messageStart": {"role": "assistant"}}

        if turn.tool_calls:
            for position, call in enumerate(turn.tool_calls):
                self.calls_seen.append(call.name)
                yield {
                    "contentBlockStart": {
                        "start": {"toolUse": {"toolUseId": f"tu-{uuid.uuid4().hex[:8]}", "name": call.name}},
                        "contentBlockIndex": position,
                    }
                }
                yield {
                    "contentBlockDelta": {
                        "delta": {"toolUse": {"input": json.dumps(call.arguments)}},
                        "contentBlockIndex": position,
                    }
                }
                yield {"contentBlockStop": {"contentBlockIndex": position}}
            yield {"messageStop": {"stopReason": "tool_use"}}
        else:
            yield {"contentBlockDelta": {"delta": {"text": turn.text or ""}, "contentBlockIndex": 0}}
            yield {"contentBlockStop": {"contentBlockIndex": 0}}
            yield {"messageStop": {"stopReason": "end_turn"}}

        yield {
            "metadata": {
                "usage": {"inputTokens": 1, "outputTokens": 1, "totalTokens": 2},
                "metrics": {"latencyMs": 1},
            }
        }

    async def structured_output(self, output_model, prompt, system_prompt=None, **kwargs):
        yield {"output": output_model()}
