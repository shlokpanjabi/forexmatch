"""Pure data types for the recommendation engine.

Nothing here imports SQLAlchemy. ``CardFacts`` is a plain snapshot of a card, so
``recommend()`` can be exercised in unit tests with hand-written fixtures and no
database — which is what makes the determinism requirement (BUILD.md section 95)
checkable rather than aspirational.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.enums import (
    BenefitType,
    CardNetwork,
    CardType,
    Confidence,
    EligibilityCriterion,
    FeeType,
    Freshness,
    LimitType,
    ScoreComponent,
    SourceType,
)

# --- Freshness ---------------------------------------------------------------

#: BUILD.md section 56.
FRESHNESS_THRESHOLDS_DAYS: tuple[tuple[int, Freshness], ...] = (
    (7, Freshness.FRESH),
    (30, Freshness.RECENT),
    (90, Freshness.AGING),
)


def classify_freshness(verified_at: datetime | None, *, now: datetime | None = None) -> Freshness:
    if verified_at is None:
        return Freshness.UNKNOWN
    now = now or datetime.now(UTC)
    if verified_at.tzinfo is None:
        verified_at = verified_at.replace(tzinfo=UTC)
    age_days = (now - verified_at).days
    for threshold, level in FRESHNESS_THRESHOLDS_DAYS:
        if age_days < threshold:
            return level
    return Freshness.STALE


# --- Card snapshot -----------------------------------------------------------


class SourceFact(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: uuid.UUID
    url: str
    domain: str
    title: str | None = None
    source_type: SourceType
    retrieved_at: datetime
    last_verified_at: datetime

    @property
    def is_official(self) -> bool:
        return self.source_type is not SourceType.SECONDARY_SOURCE


class CurrencyFact(BaseModel):
    model_config = ConfigDict(frozen=True)

    currency_code: str
    supported: bool = True
    direct_wallet: bool = True


class FeeFact(BaseModel):
    """A single published charge.

    ``amount``/``percentage`` are None when unverified. ``is_waived`` is the only
    way to express a genuine zero, so "we don't know" can never be read as free.
    """

    model_config = ConfigDict(frozen=True)

    fee_type: FeeType
    amount: Decimal | None = None
    currency: str | None = None
    percentage: Decimal | None = None
    min_amount: Decimal | None = None
    max_amount: Decimal | None = None
    is_unknown: bool = False
    is_waived: bool = False
    conditions: str | None = None

    @property
    def is_known(self) -> bool:
        return self.is_waived or self.amount is not None or self.percentage is not None

    @property
    def effective_amount(self) -> Decimal | None:
        if self.is_waived:
            return Decimal(0)
        return self.amount

    @property
    def effective_percentage(self) -> Decimal | None:
        if self.is_waived:
            return Decimal(0)
        return self.percentage


class LimitFact(BaseModel):
    model_config = ConfigDict(frozen=True)

    limit_type: LimitType
    amount: Decimal | None = None
    currency: str | None = None
    period: str | None = None


class BenefitFact(BaseModel):
    model_config = ConfigDict(frozen=True)

    benefit_type: BenefitType
    description: str
    value: str | None = None


class EligibilityFact(BaseModel):
    model_config = ConfigDict(frozen=True)

    criterion: EligibilityCriterion
    value: str | None = None
    description: str


class CardFacts(BaseModel):
    """Everything the engine knows about one card."""

    model_config = ConfigDict(frozen=True)

    id: uuid.UUID
    provider: str
    card_name: str
    slug: str
    card_type: CardType
    network: CardNetwork = CardNetwork.UNKNOWN
    description: str | None = None
    is_active: bool = True
    application_url: str | None = None
    affiliate_url: str | None = None
    affiliate_tracking_enabled: bool = False
    last_verified_at: datetime | None = None

    currencies: tuple[CurrencyFact, ...] = ()
    fees: tuple[FeeFact, ...] = ()
    limits: tuple[LimitFact, ...] = ()
    benefits: tuple[BenefitFact, ...] = ()
    eligibility: tuple[EligibilityFact, ...] = ()
    sources: tuple[SourceFact, ...] = ()

    # --- Lookups ------------------------------------------------------------

    def fee(self, fee_type: FeeType, currency: str | None = None) -> FeeFact | None:
        """The applicable fee of a type, preferring one with a usable value.

        Providers commonly publish a *different* figure per currency — Axis
        charges GBP 1.41 but USD 2.25 to withdraw cash — so a lookup without a
        currency would quietly price the wrong one. Resolution order:

        1. a fee denominated in the requested currency;
        2. a percentage-only fee, which applies whatever the currency;
        3. a rupee-denominated fee (issuance and reload are charged in INR);
        4. the single published figure, if there is exactly one;

        and otherwise ``None`` — meaning "not published for this currency",
        which the calculator then imputes pessimistically rather than treating
        as free.
        """
        matches = [f for f in self.fees if f.fee_type is fee_type]
        if not matches:
            return None
        known = [f for f in matches if f.is_known] or matches
        if currency is None:
            return known[0]

        wanted = currency.upper()
        for candidate in known:
            if candidate.currency and candidate.currency.upper() == wanted:
                return candidate
        for candidate in known:
            if candidate.currency is None and candidate.percentage is not None:
                return candidate
        for candidate in known:
            if candidate.currency and candidate.currency.upper() == "INR":
                return candidate
        return known[0] if len(known) == 1 else None

    def currency(self, code: str) -> CurrencyFact | None:
        code = code.upper()
        for entry in self.currencies:
            if entry.currency_code.upper() == code:
                return entry
        return None

    def supports_currency(self, code: str) -> bool:
        entry = self.currency(code)
        return bool(entry and entry.supported)

    def has_direct_wallet(self, code: str) -> bool:
        entry = self.currency(code)
        return bool(entry and entry.supported and entry.direct_wallet)

    def has_benefit(self, benefit_type: BenefitType) -> bool:
        return any(b.benefit_type is benefit_type for b in self.benefits)

    def limit(self, limit_type: LimitType) -> LimitFact | None:
        for entry in self.limits:
            if entry.limit_type is limit_type:
                return entry
        return None

    @property
    def supported_currency_codes(self) -> list[str]:
        return sorted(c.currency_code.upper() for c in self.currencies if c.supported)

    @property
    def freshness(self) -> Freshness:
        return classify_freshness(self.last_verified_at)

    @property
    def official_sources(self) -> list[SourceFact]:
        return [s for s in self.sources if s.is_official]

    @property
    def apply_url(self) -> str | None:
        """Affiliate link when configured, else the official one (section 53).

        Ranking never sees this — it is resolved only after a winner is chosen.
        """
        if self.affiliate_tracking_enabled and self.affiliate_url:
            return self.affiliate_url
        return self.application_url


# --- Cost --------------------------------------------------------------------


class CostComponent(BaseModel):
    """One line of the cost estimate, with the arithmetic shown."""

    model_config = ConfigDict(frozen=True)

    fee_type: FeeType
    label: str
    amount_inr: Decimal
    basis: str
    #: True when the provider publishes nothing and we substituted the worst
    #: value in the candidate set rather than assuming zero (section 58).
    is_imputed: bool = False
    imputation_note: str | None = None


class CostBreakdown(BaseModel):
    model_config = ConfigDict(frozen=True)

    card_id: uuid.UUID
    components: tuple[CostComponent, ...] = ()
    total_inr: Decimal = Decimal(0)
    total_spend_currency: Decimal | None = None
    spend_currency: str | None = None
    duration_months: int = 12
    #: Components we could neither verify nor impute — excluded from the total,
    #: which therefore understates the true cost.
    unknown_components: tuple[FeeType, ...] = ()
    imputed_components: tuple[FeeType, ...] = ()
    assumptions: tuple[str, ...] = ()
    fx_rate_used: str | None = None
    fx_retrieved_at: datetime | None = None

    @property
    def is_complete(self) -> bool:
        return not self.unknown_components and not self.imputed_components

    @property
    def total_is_lower_bound(self) -> bool:
        return bool(self.unknown_components)


# --- Scoring -----------------------------------------------------------------


class ComponentScore(BaseModel):
    model_config = ConfigDict(frozen=True)

    component: ScoreComponent
    score: float = Field(ge=0.0, le=100.0)
    weight: float = Field(ge=0.0, le=1.0)
    explanation: str

    @property
    def weighted(self) -> float:
        return self.score * self.weight


class CardEvaluation(BaseModel):
    """A fully scored candidate."""

    model_config = ConfigDict(frozen=True)

    card: CardFacts
    cost: CostBreakdown
    scores: tuple[ComponentScore, ...]
    final_score: float
    key_reasons: tuple[str, ...] = ()
    downsides: tuple[str, ...] = ()
    best_for: tuple[str, ...] = ()

    @property
    def match_percentage(self) -> int:
        """Rounded to a whole number — 93.7284% is false precision (section 22)."""
        return round(self.final_score)

    def score_for(self, component: ScoreComponent) -> ComponentScore | None:
        for entry in self.scores:
            if entry.component is component:
                return entry
        return None


class ExcludedCard(BaseModel):
    model_config = ConfigDict(frozen=True)

    card_id: uuid.UUID
    provider: str
    card_name: str
    reason: str


class RecommendationResult(BaseModel):
    """The engine's complete, self-explaining output (BUILD.md section 30)."""

    model_config = ConfigDict(frozen=True)

    recommended: CardEvaluation | None = None
    alternatives: tuple[CardEvaluation, ...] = ()
    comparison: tuple[CardEvaluation, ...] = ()
    excluded: tuple[ExcludedCard, ...] = ()
    assumptions: tuple[str, ...] = ()
    confidence: Confidence = Confidence.MEDIUM
    confidence_reasons: tuple[str, ...] = ()
    #: Cards within the tie threshold of the winner (section 60).
    tied_with_recommended: tuple[uuid.UUID, ...] = ()
    weights_used: dict[str, float] = Field(default_factory=dict)
    weights_were_customised: bool = False
    spend_currency: str | None = None
    duration_months: int = 12
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def has_recommendation(self) -> bool:
        return self.recommended is not None

    @property
    def all_sources(self) -> list[SourceFact]:
        seen: dict[str, SourceFact] = {}
        for evaluation in self.comparison:
            for source in evaluation.card.sources:
                seen.setdefault(source.url, source)
        return sorted(seen.values(), key=lambda s: (s.domain, s.url))
