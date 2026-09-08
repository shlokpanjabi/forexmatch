"""Model configuration.

The agent never names a model. It asks this factory, which reads the
environment — so switching model or provider is a config change, not a code
change (BUILD.md section 75).
"""

from __future__ import annotations

from collections.abc import AsyncIterable
from typing import Any

import structlog
from strands.models.model import Model

from app.config import Settings, get_settings

logger = structlog.get_logger(__name__)


class MockModel(Model):
    """Deterministic offline model.

    Lets the whole pipeline — API, persistence, tool wiring, the frontend — be
    exercised without AWS credentials. It answers in fixed text and calls no
    tools, so it is never mistaken for the real agent.
    """

    def __init__(self, reply: str | None = None) -> None:
        self._config: dict[str, Any] = {"model_id": "mock"}
        self._reply = reply or (
            "I'm running without a language model configured, so I can't hold a real "
            "conversation. The recommendation engine, card data and FX rates all still "
            "work — set MODEL_PROVIDER=bedrock with AWS credentials to enable the agent."
        )

    def update_config(self, **model_config: Any) -> None:
        self._config.update(model_config)

    def get_config(self) -> Any:
        return self._config

    async def stream(self, messages, tool_specs=None, system_prompt=None, **kwargs) -> AsyncIterable[Any]:
        yield {"messageStart": {"role": "assistant"}}
        yield {"contentBlockDelta": {"delta": {"text": self._reply}}}
        yield {"contentBlockStop": {}}
        yield {"messageStop": {"stopReason": "end_turn"}}
        yield {
            "metadata": {
                "usage": {"inputTokens": 0, "outputTokens": 0, "totalTokens": 0},
                "metrics": {"latencyMs": 0},
            }
        }

    async def structured_output(self, output_model, prompt, system_prompt=None, **kwargs):
        yield {"output": output_model()}


def build_model(settings: Settings | None = None) -> Model:
    settings = settings or get_settings()

    if settings.model_provider == "mock":
        logger.info("model.mock_selected")
        return MockModel()

    from strands.models import BedrockModel

    logger.info(
        "model.bedrock_selected", model_id=settings.bedrock_model_id, region=settings.aws_region
    )
    # Credentials come from the standard boto3 chain — env, ~/.aws, SSO or an
    # instance role. Nothing secret is read from settings.
    return BedrockModel(
        model_id=settings.bedrock_model_id,
        region_name=settings.aws_region,
        max_tokens=settings.bedrock_max_tokens,
        temperature=settings.bedrock_temperature,
        streaming=settings.bedrock_streaming,
    )
