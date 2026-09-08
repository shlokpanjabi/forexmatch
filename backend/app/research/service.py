"""Web research for verifying card facts (BUILD.md sections 41, 65).

Research exists to *check* the catalogue, never to replace it. Two rules hold
whatever the provider does:

* Queries prefer official provider domains, because a blog is never a better
  source than a published fee schedule (section 13).
* If research is unavailable, the tool says so. It never falls back to the
  model's own recollection of a fee — that is precisely the failure mode this
  product exists to avoid (section 65).
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal
from urllib.parse import urlparse

import structlog

from app.config import Settings, get_settings

logger = structlog.get_logger(__name__)

#: Official domains we trust for Indian forex-card facts.
PROVIDER_DOMAINS: dict[str, tuple[str, ...]] = {
    "HDFC Bank": ("hdfcbank.com", "hdfc.bank.in"),
    "Axis Bank": ("axisbank.com", "axis.bank.in"),
    "ICICI Bank": ("icicibank.com", "icici.bank.in"),
    "YES BANK": ("yesbank.in",),
    "BookMyForex": ("bookmyforex.com",),
    "Thomas Cook": ("thomascook.in",),
    "Orient Exchange": ("orientexchange.in",),
}


@dataclass
class ResearchFinding:
    url: str
    title: str | None
    domain: str
    snippet: str
    retrieved_at: datetime

    @property
    def is_official(self) -> bool:
        return any(self.domain.endswith(d) for domains in PROVIDER_DOMAINS.values() for d in domains)

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "title": self.title,
            "domain": self.domain,
            "snippet": self.snippet,
            "retrieved_at": self.retrieved_at.isoformat(),
            "is_official_domain": self.is_official,
        }


@dataclass
class ResearchResult:
    status: Literal["ok", "unavailable"]
    query: str
    findings: list[ResearchFinding] = field(default_factory=list)
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "query": self.query,
            "findings": [f.to_dict() for f in self.findings],
            "reason": self.reason,
            "note": (
                "Findings are raw retrieved text. Do not treat them as verified card data; "
                "propose a verification change instead."
                if self.status == "ok"
                else "Research is unavailable. Use the verified database values and say that "
                "current figures could not be re-checked."
            ),
        }


def build_query(provider: str, card_name: str, topic: str) -> str:
    """Bias the query towards the provider's own site."""
    domains = PROVIDER_DOMAINS.get(provider, ())
    site = f"site:{domains[0]} " if domains else ""
    return f"{site}{card_name} {topic}".strip()


class ResearchService:
    """Retrieves current provider information via Bedrock's web search tool."""

    def __init__(self, settings: Settings | None = None, client: Any | None = None) -> None:
        self._settings = settings or get_settings()
        self._client = client

    def _bedrock(self) -> Any:
        if self._client is None:
            import boto3

            self._client = boto3.client("bedrock-runtime", region_name=self._settings.aws_region)
        return self._client

    async def search(self, provider: str, card_name: str, topic: str) -> ResearchResult:
        query = build_query(provider, card_name, topic)

        if self._settings.research_provider == "none":
            return ResearchResult(
                status="unavailable",
                query=query,
                reason="Web research is disabled by configuration (RESEARCH_PROVIDER=none).",
            )

        try:
            return await asyncio.to_thread(self._search_sync, query)
        except Exception as exc:  # noqa: BLE001 — degrade, never fabricate
            logger.warning("research.unavailable", query=query, error=str(exc))
            return ResearchResult(
                status="unavailable",
                query=query,
                reason=(
                    "Bedrock web search is not available for this account. Built-in tools require "
                    "the Anthropic use-case details form to be submitted in the AWS console. "
                    f"Underlying error: {exc}"
                ),
            )

    def _search_sync(self, query: str) -> ResearchResult:
        """Invoke Converse with the built-in web search system tool."""
        response = self._bedrock().converse(
            modelId=self._settings.bedrock_model_id,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "text": (
                                f"Search the web for: {query}\n\n"
                                "Return only what the pages actually say about the published "
                                "charges. Do not estimate or infer any figure."
                            )
                        }
                    ],
                }
            ],
            inferenceConfig={"maxTokens": 2048, "temperature": 0},
            toolConfig={"tools": [{"systemTool": {"name": "web_search"}}]},
        )
        return self._parse(query, response)

    def _parse(self, query: str, response: dict) -> ResearchResult:
        findings: list[ResearchFinding] = []
        now = datetime.now(UTC)
        limit = self._settings.research_max_results

        for block in response.get("output", {}).get("message", {}).get("content", []):
            citations = block.get("citationsContent") or {}
            for citation in citations.get("citations", []):
                location = citation.get("location", {}) or {}
                url = location.get("url") or citation.get("sourceUrl")
                if not url:
                    continue
                findings.append(
                    ResearchFinding(
                        url=url,
                        title=citation.get("title"),
                        domain=urlparse(url).netloc,
                        snippet=json.dumps(citation.get("sourceContent", ""))[:800],
                        retrieved_at=now,
                    )
                )
            for result in (block.get("toolResult", {}) or {}).get("content", []):
                payload = result.get("json") or {}
                for item in payload.get("results", [])[:limit]:
                    url = item.get("url")
                    if not url:
                        continue
                    findings.append(
                        ResearchFinding(
                            url=url,
                            title=item.get("title"),
                            domain=urlparse(url).netloc,
                            snippet=(item.get("content") or item.get("snippet") or "")[:800],
                            retrieved_at=now,
                        )
                    )

        if not findings:
            return ResearchResult(
                status="unavailable",
                query=query,
                reason="The search returned no citable sources.",
            )

        # Official sources first — trust hierarchy, section 13.
        findings.sort(key=lambda f: (not f.is_official, f.domain))
        return ResearchResult(status="ok", query=query, findings=findings[:limit])
