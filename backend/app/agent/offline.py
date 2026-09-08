"""An offline model that exercises the real pipeline without a provider.

Selected with ``MODEL_PROVIDER=mock``. It lets the whole product be run and
demonstrated with no AWS access at all — and, importantly, it does not fake any
of the work. It calls the *real* tools against the *real* catalogue, the real FX
service and the real ranking engine, so every tool event in the activity feed is
genuine and the recommendation is the one the deterministic engine produced.

What it replaces is only the language understanding: instead of a model reading
the message, it does crude keyword matching. That is obviously not the product —
it cannot handle nuance, ambiguity or follow-up — and it says so in its replies
so it can never be mistaken for the agent.
"""

from __future__ import annotations

import json
import re
import uuid
from collections.abc import AsyncIterable
from typing import Any

from strands.models.model import Model

#: Place names common enough among Indian students to be worth matching.
COUNTRY_HINTS: tuple[tuple[tuple[str, ...], str, str], ...] = (
    (("uk", "united kingdom", "britain", "england", "london", "manchester", "scotland"), "United Kingdom", "GBP"),
    (("usa", "u.s.", "the us ", "in the us", "united states", "america", "new york", "boston", "california"), "United States", "USD"),
    (("germany", "berlin", "munich", "netherlands", "france", "paris", "spain", "italy", "ireland", "dublin", "europe"), "Europe", "EUR"),
    (("canada", "toronto", "vancouver", "montreal"), "Canada", "CAD"),
    (("australia", "sydney", "melbourne"), "Australia", "AUD"),
    (("singapore",), "Singapore", "SGD"),
    (("dubai", "uae", "abu dhabi"), "United Arab Emirates", "AED"),
)

SYMBOL_CURRENCIES = {"£": "GBP", "$": "USD", "€": "EUR", "₹": "INR"}

#: "a two year master's" is at least as common as "24 months".
WORD_NUMBERS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}

CASH_HINTS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("no cash", "never withdraw", "won't use cash", "wont use cash", "no atm"), "none"),
    (("not much cash", "rarely", "hardly", "barely", "little cash", "won't withdraw much", "wont withdraw much"), "low"),
    (("twice a week", "every week", "weekly", "lots of cash", "a lot of cash", "often"), "high"),
    (("sometimes", "occasionally", "now and then"), "medium"),
)

PRIORITY_HINTS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("cheapest", "lowest cost", "keep fees low", "low fees", "save money", "cost"), "priority_cost"),
    (("lounge", "rewards", "cashback", "points", "perks", "benefits"), "priority_rewards"),
    (("atm", "cash withdrawal", "withdraw cash"), "priority_atm"),
    (("convenient", "convenience", "easy", "quick"), "priority_convenience"),
    (("safe", "security", "fraud", "secure"), "priority_security"),
)

NOTICE = (
    "Note: this reply came from the offline demo model (MODEL_PROVIDER=mock), which matches "
    "keywords rather than reading your message. The card data, exchange rate, cost calculation "
    "and ranking below are all real. Configure Amazon Bedrock for the actual agent."
)


def extract_profile(text: str) -> dict[str, Any]:
    """Best-effort keyword extraction. Deliberately conservative."""
    lowered = text.lower()
    updates: dict[str, Any] = {}

    for needles, country, currency in COUNTRY_HINTS:
        if any(needle in lowered for needle in needles):
            updates["destination_country"] = country
            updates["destination_currency"] = currency
            break

    # "£1,000 to £1,200", "around 900 euros", "$1500 a month"
    amounts = [
        float(match.replace(",", ""))
        for match in re.findall(r"(?:[£$€₹]\s?)?(\d[\d,]{2,})", lowered)
        if 50 <= float(match.replace(",", "")) <= 100_000
    ]
    words = "|".join(WORD_NUMBERS)
    years = re.search(rf"(\d+|{words})\s*(?:-|\s)?\s*years?", lowered)
    months_only = re.search(rf"(\d+|{words})\s*(?:-|\s)?\s*months?", lowered)
    if years:
        token = years.group(1)
        count = WORD_NUMBERS.get(token) or int(token)
        updates["trip_duration_months"] = count * 12
        amounts = [a for a in amounts if a != float(count)]
    elif months_only:
        token = months_only.group(1)
        updates["trip_duration_months"] = WORD_NUMBERS.get(token) or int(token)

    spend = [a for a in amounts if a >= 100]
    if spend:
        updates["monthly_spend_min"] = min(spend)
        updates["monthly_spend_max"] = max(spend)
        updates["spend_is_estimate"] = len(set(spend)) > 1 or "around" in lowered or "maybe" in lowered
        for symbol, code in SYMBOL_CURRENCIES.items():
            if symbol in text:
                updates["monthly_spend_currency"] = code
                break
        else:
            updates["monthly_spend_currency"] = updates.get("destination_currency")

    for needles, usage in CASH_HINTS:
        if any(needle in lowered for needle in needles):
            updates["atm_usage"] = usage
            break

    for needles, field in PRIORITY_HINTS:
        if any(needle in lowered for needle in needles):
            updates[field] = 0.8
            break

    if "student" in lowered or "master" in lowered or "university" in lowered or "study" in lowered:
        updates["student_status"] = True
        updates["trip_type"] = "study"

    return {k: v for k, v in updates.items() if v is not None}


class OfflineDemoModel(Model):
    """Drives the real tool sequence from keyword-extracted input."""

    def __init__(self) -> None:
        self._config: dict[str, Any] = {"model_id": "offline-demo"}
        self._step = 0

    def update_config(self, **model_config: Any) -> None:
        self._config.update(model_config)

    def get_config(self) -> Any:
        return self._config

    @staticmethod
    def _latest_user_text(messages: list[dict[str, Any]]) -> str:
        for message in reversed(messages):
            if message.get("role") != "user":
                continue
            for block in message.get("content", []) or []:
                if isinstance(block, dict) and isinstance(block.get("text"), str):
                    return block["text"]
        return ""

    @staticmethod
    def _winner_from_history(messages: list[dict[str, Any]]) -> str | None:
        """Read the ranking out of the compare_cards tool result."""
        for message in reversed(messages):
            for block in message.get("content", []) or []:
                if not isinstance(block, dict):
                    continue
                result = block.get("toolResult")
                if not result:
                    continue
                for item in result.get("content", []) or []:
                    raw = item.get("text") if isinstance(item, dict) else None
                    if not raw or "recommended_card" not in raw:
                        continue
                    try:
                        payload = json.loads(raw)
                    except (TypeError, ValueError):
                        continue
                    card = (payload or {}).get("recommended_card")
                    if card:
                        return f"{card['card']['provider']} — {card['card']['card_name']}"
        return None

    async def stream(self, messages, tool_specs=None, system_prompt=None, **kwargs) -> AsyncIterable[Any]:
        step = self._step
        self._step += 1

        plan: list[tuple[str, dict[str, Any]]] = []
        if step == 0:
            updates = extract_profile(self._latest_user_text(messages))
            if updates:
                plan.append(("update_user_profile", updates))
        elif step == 1:
            plan.append(("search_cards", {}))
        elif step == 2:
            plan.append(("get_fx_rate", {"base_currency": "GBP", "quote_currency": "INR"}))
        elif step == 3:
            plan.append(("compare_cards", {}))

        yield {"messageStart": {"role": "assistant"}}

        if plan:
            for index, (name, arguments) in enumerate(plan):
                yield {
                    "contentBlockStart": {
                        "start": {"toolUse": {"toolUseId": f"tu-{uuid.uuid4().hex[:8]}", "name": name}},
                        "contentBlockIndex": index,
                    }
                }
                yield {
                    "contentBlockDelta": {
                        "delta": {"toolUse": {"input": json.dumps(arguments)}},
                        "contentBlockIndex": index,
                    }
                }
                yield {"contentBlockStop": {"contentBlockIndex": index}}
            yield {"messageStop": {"stopReason": "tool_use"}}
        else:
            winner = self._winner_from_history(messages)
            text = (
                f"Based on your usage, the deterministic engine ranked {winner} highest. "
                "The full comparison, cost breakdown and sources are below.\n\n"
                if winner
                else "I could not work out enough from that message to compare cards. "
                "Try naming the country, roughly what you'll spend a month, and how long you're going for.\n\n"
            )
            yield {"contentBlockDelta": {"delta": {"text": text + NOTICE}, "contentBlockIndex": 0}}
            yield {"contentBlockStop": {"contentBlockIndex": 0}}
            yield {"messageStop": {"stopReason": "end_turn"}}

        yield {
            "metadata": {
                "usage": {"inputTokens": 0, "outputTokens": 0, "totalTokens": 0},
                "metrics": {"latencyMs": 0},
            }
        }

    async def structured_output(self, output_model, prompt, system_prompt=None, **kwargs):
        yield {"output": output_model()}
