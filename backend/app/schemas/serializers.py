"""Shared JSON shapes for tools and the HTTP API.

One definition, used by both, so what the agent reads and what the browser
renders can never drift apart.
"""

from __future__ import annotations

from typing import Any

from app.recommendation.models import (
    CardEvaluation,
    CardFacts,
    CostBreakdown,
    RecommendationResult,
)


def fee_to_dict(fee) -> dict[str, Any]:
    return {
        "fee_type": fee.fee_type.value,
        "amount": str(fee.amount) if fee.amount is not None else None,
        "currency": fee.currency,
        "percentage": str(fee.percentage) if fee.percentage is not None else None,
        "min_amount": str(fee.min_amount) if fee.min_amount is not None else None,
        "max_amount": str(fee.max_amount) if fee.max_amount is not None else None,
        # The three-way distinction that keeps unknown from meaning free.
        "is_unknown": fee.is_unknown,
        "is_waived": fee.is_waived,
        "conditions": fee.conditions,
    }


def source_to_dict(source) -> dict[str, Any]:
    return {
        "url": source.url,
        "domain": source.domain,
        "title": source.title,
        "source_type": source.source_type.value,
        "is_official": source.is_official,
        "last_verified_at": source.last_verified_at.isoformat(),
    }


def card_summary(card: CardFacts) -> dict[str, Any]:
    return {
        "id": str(card.id),
        "slug": card.slug,
        "provider": card.provider,
        "card_name": card.card_name,
        "card_type": card.card_type.value,
        "network": card.network.value,
        "description": card.description,
        "supported_currencies": card.supported_currency_codes,
        "currency_support_verified": bool(card.currencies),
        "freshness": card.freshness.value,
        "last_verified_at": card.last_verified_at.isoformat() if card.last_verified_at else None,
    }


def card_detail(card: CardFacts) -> dict[str, Any]:
    return card_summary(card) | {
        "application_url": card.application_url,
        "fees": [fee_to_dict(f) for f in card.fees],
        "limits": [
            {
                "limit_type": limit.limit_type.value,
                "amount": str(limit.amount) if limit.amount is not None else None,
                "currency": limit.currency,
                "period": limit.period,
            }
            for limit in card.limits
        ],
        "benefits": [
            {"benefit_type": b.benefit_type.value, "description": b.description, "value": b.value}
            for b in card.benefits
        ],
        "eligibility": [
            {"criterion": e.criterion.value, "value": e.value, "description": e.description}
            for e in card.eligibility
        ],
        "currencies": [
            {"code": c.currency_code, "supported": c.supported, "direct_wallet": c.direct_wallet}
            for c in card.currencies
        ],
        "sources": [source_to_dict(s) for s in card.sources],
    }


def cost_to_dict(cost: CostBreakdown) -> dict[str, Any]:
    return {
        "total_inr": str(cost.total_inr),
        "total_spend_currency": str(cost.total_spend_currency) if cost.total_spend_currency else None,
        "spend_currency": cost.spend_currency,
        "duration_months": cost.duration_months,
        "total_is_lower_bound": cost.total_is_lower_bound,
        "components": [
            {
                "fee_type": c.fee_type.value,
                "label": c.label,
                "amount_inr": str(c.amount_inr),
                "basis": c.basis,
                "is_imputed": c.is_imputed,
                "imputation_note": c.imputation_note,
            }
            for c in cost.components
        ],
        "unknown_components": [f.value for f in cost.unknown_components],
        "imputed_components": [f.value for f in cost.imputed_components],
        "assumptions": list(cost.assumptions),
        "fx_rate_used": cost.fx_rate_used,
        "fx_retrieved_at": cost.fx_retrieved_at.isoformat() if cost.fx_retrieved_at else None,
    }


def evaluation_to_dict(evaluation: CardEvaluation) -> dict[str, Any]:
    return {
        "card": card_summary(evaluation.card),
        "match_score": evaluation.match_percentage,
        "estimated_cost": cost_to_dict(evaluation.cost),
        "scores": [
            {
                "component": s.component.value,
                "score": round(s.score),
                "weight": s.weight,
                "explanation": s.explanation,
            }
            for s in evaluation.scores
        ],
        "key_reasons": list(evaluation.key_reasons),
        "downsides": list(evaluation.downsides),
        "best_for": list(evaluation.best_for),
        "application_url": evaluation.card.apply_url,
        "sources": [source_to_dict(s) for s in evaluation.card.sources],
        "last_verified": (
            evaluation.card.last_verified_at.isoformat() if evaluation.card.last_verified_at else None
        ),
    }


def recommendation_to_dict(result: RecommendationResult) -> dict[str, Any]:
    return {
        "recommended_card": evaluation_to_dict(result.recommended) if result.recommended else None,
        "alternatives": [evaluation_to_dict(e) for e in result.alternatives],
        "comparison": [evaluation_to_dict(e) for e in result.comparison],
        "excluded": [
            {"card_name": e.card_name, "provider": e.provider, "reason": e.reason}
            for e in result.excluded
        ],
        "assumptions": list(result.assumptions),
        "confidence": result.confidence.value,
        "confidence_reasons": list(result.confidence_reasons),
        "tied_with_recommended": [str(i) for i in result.tied_with_recommended],
        "weights_used": result.weights_used,
        "weights_were_customised": result.weights_were_customised,
        "spend_currency": result.spend_currency,
        "duration_months": result.duration_months,
        "sources": [source_to_dict(s) for s in result.all_sources],
        "generated_at": result.generated_at.isoformat(),
        "disclaimer": (
            "This is an informational comparison, not financial advice. Card fees and terms "
            "can change. Check the provider's current terms before applying."
        ),
    }
