"""The structured user profile the agent fills in and the engine consumes.

Two ideas drive the design:

* **Uncertainty is first class** (BUILD.md section 9). Students rarely know what
  they will spend. Spend is a range, and every derived number records whether it
  was stated, estimated or assumed, so the UI can say "estimated £900–£1,300"
  instead of inventing precision.
* **Priorities are weights, not flags** (section 11). Defaults are supplied, the
  user may override any of them, and they are always normalised to sum to 1.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.enums import AtmUsage, TripType, ValueConfidence, ScoreComponent

#: BUILD.md section 11.
DEFAULT_WEIGHTS: dict[ScoreComponent, float] = {
    ScoreComponent.COST: 0.40,
    ScoreComponent.ATM: 0.15,
    ScoreComponent.CURRENCY_SUPPORT: 0.15,
    ScoreComponent.CONVENIENCE: 0.15,
    ScoreComponent.REWARDS: 0.10,
    ScoreComponent.SECURITY: 0.05,
}

#: Expected withdrawals per month implied by a qualitative answer. Used only
#: when the user gives no number; always surfaced as an assumption.
ATM_USAGE_TO_WITHDRAWALS: dict[AtmUsage, int] = {
    AtmUsage.NONE: 0,
    AtmUsage.LOW: 1,
    AtmUsage.MEDIUM: 4,
    AtmUsage.HIGH: 10,
}


class PriorityWeights(BaseModel):
    """Normalised preference weights across the six scoring components."""

    model_config = ConfigDict(extra="forbid")

    cost: float = Field(default=DEFAULT_WEIGHTS[ScoreComponent.COST], ge=0.0)
    atm: float = Field(default=DEFAULT_WEIGHTS[ScoreComponent.ATM], ge=0.0)
    currency_support: float = Field(default=DEFAULT_WEIGHTS[ScoreComponent.CURRENCY_SUPPORT], ge=0.0)
    convenience: float = Field(default=DEFAULT_WEIGHTS[ScoreComponent.CONVENIENCE], ge=0.0)
    rewards: float = Field(default=DEFAULT_WEIGHTS[ScoreComponent.REWARDS], ge=0.0)
    security: float = Field(default=DEFAULT_WEIGHTS[ScoreComponent.SECURITY], ge=0.0)

    def as_dict(self) -> dict[ScoreComponent, float]:
        return {
            ScoreComponent.COST: self.cost,
            ScoreComponent.ATM: self.atm,
            ScoreComponent.CURRENCY_SUPPORT: self.currency_support,
            ScoreComponent.CONVENIENCE: self.convenience,
            ScoreComponent.REWARDS: self.rewards,
            ScoreComponent.SECURITY: self.security,
        }

    def normalised(self) -> PriorityWeights:
        """Scale so the weights sum to exactly 1.

        An all-zero set carries no information, so it falls back to the defaults
        rather than producing a divide-by-zero or a meaningless uniform ranking.
        """
        raw = self.as_dict()
        total = sum(raw.values())
        if total <= 0:
            return PriorityWeights()
        return PriorityWeights(**{key.value: value / total for key, value in raw.items()})

    @property
    def is_normalised(self) -> bool:
        return abs(sum(self.as_dict().values()) - 1.0) < 1e-9


class SpendEstimate(BaseModel):
    """A monthly spend figure that may legitimately be a range."""

    model_config = ConfigDict(extra="forbid")

    min_amount: Decimal | None = None
    max_amount: Decimal | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    confidence: ValueConfidence = ValueConfidence.ESTIMATED

    @field_validator("currency")
    @classmethod
    def _upper(cls, value: str | None) -> str | None:
        return value.upper() if value else value

    @model_validator(mode="after")
    def _order_bounds(self) -> SpendEstimate:
        if self.min_amount is not None and self.max_amount is not None and self.min_amount > self.max_amount:
            object.__setattr__(self, "min_amount", self.max_amount)
            object.__setattr__(self, "max_amount", self.min_amount)
        return self

    @property
    def midpoint(self) -> Decimal | None:
        """Point estimate used for calculation. The range is what we display."""
        if self.min_amount is not None and self.max_amount is not None:
            return (self.min_amount + self.max_amount) / 2
        return self.min_amount if self.min_amount is not None else self.max_amount

    @property
    def is_known(self) -> bool:
        return self.midpoint is not None

    def describe(self) -> str | None:
        if not self.is_known:
            return None
        symbol = self.currency or ""
        if self.min_amount is not None and self.max_amount is not None and self.min_amount != self.max_amount:
            return f"{symbol} {self.min_amount:,.0f}–{self.max_amount:,.0f}".strip()
        return f"{symbol} {self.midpoint:,.0f}".strip()


class UserProfile(BaseModel):
    """Everything the recommendation engine is allowed to know about the user.

    Deliberately contains no identifiers — no name, no passport, no PAN, no
    account numbers (BUILD.md section 86). Every field is optional: the agent
    fills in what it can infer and asks only about what actually changes the
    outcome.
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    # --- Destination --------------------------------------------------------
    destination_country: str | None = None
    destination_currencies: list[str] = Field(default_factory=list)

    # --- Trip ---------------------------------------------------------------
    trip_type: TripType | None = None
    trip_duration_months: int | None = Field(default=None, ge=0, le=120)
    currently_abroad: bool | None = None
    departure_date: date | None = None
    student_status: bool | None = None

    # --- Spending -----------------------------------------------------------
    monthly_spend: SpendEstimate = Field(default_factory=SpendEstimate)
    primary_spending_categories: list[str] = Field(default_factory=list)

    # --- Cash ---------------------------------------------------------------
    atm_usage: AtmUsage = AtmUsage.UNKNOWN
    atm_withdrawals_per_month: int | None = Field(default=None, ge=0, le=200)
    average_atm_withdrawal: Decimal | None = Field(default=None, ge=0)

    # --- Reloads and currencies --------------------------------------------
    expected_reload_frequency: int | None = Field(
        default=None, ge=0, le=60, description="Reloads per month."
    )
    needs_multiple_currencies: bool | None = None

    # --- Priorities ---------------------------------------------------------
    priorities: PriorityWeights = Field(default_factory=PriorityWeights)
    #: True once the user has actually expressed a preference, so the engine can
    #: report whether ranking used their weights or ours.
    priorities_customised: bool = False

    @field_validator("destination_currencies")
    @classmethod
    def _normalise_currencies(cls, value: list[str]) -> list[str]:
        seen: list[str] = []
        for code in value:
            upper = code.strip().upper()
            if len(upper) == 3 and upper not in seen:
                seen.append(upper)
        return seen

    # --- Derived values -----------------------------------------------------

    @property
    def primary_currency(self) -> str | None:
        if self.destination_currencies:
            return self.destination_currencies[0]
        return self.monthly_spend.currency

    @property
    def effective_duration_months(self) -> int:
        """Months to price over. Defaults to 12 so costs are comparable."""
        return self.trip_duration_months if self.trip_duration_months else 12

    @property
    def duration_is_assumed(self) -> bool:
        return not self.trip_duration_months

    def effective_atm_withdrawals_per_month(self) -> tuple[int, ValueConfidence]:
        """Withdrawals per month, plus how firmly we know it."""
        if self.atm_withdrawals_per_month is not None:
            return self.atm_withdrawals_per_month, ValueConfidence.STATED
        if self.atm_usage in ATM_USAGE_TO_WITHDRAWALS:
            return ATM_USAGE_TO_WITHDRAWALS[self.atm_usage], ValueConfidence.ESTIMATED
        return ATM_USAGE_TO_WITHDRAWALS[AtmUsage.LOW], ValueConfidence.ASSUMED

    def effective_reloads_per_month(self) -> tuple[int, ValueConfidence]:
        if self.expected_reload_frequency is not None:
            return self.expected_reload_frequency, ValueConfidence.STATED
        return 1, ValueConfidence.ASSUMED

    @property
    def is_ready_for_recommendation(self) -> bool:
        """The minimum needed to produce a defensible comparison: where they are
        going, and roughly what they will spend."""
        return bool(self.primary_currency) and self.monthly_spend.is_known

    def missing_high_value_fields(self) -> list[str]:
        """Questions worth asking, in priority order (BUILD.md section 10)."""
        missing: list[str] = []
        if not self.destination_country and not self.destination_currencies:
            missing.append("destination_country")
        if not self.monthly_spend.is_known:
            missing.append("monthly_spend")
        if not self.trip_duration_months:
            missing.append("trip_duration_months")
        if self.atm_usage is AtmUsage.UNKNOWN and self.atm_withdrawals_per_month is None:
            missing.append("atm_usage")
        if self.needs_multiple_currencies is None:
            missing.append("needs_multiple_currencies")
        if not self.priorities_customised:
            missing.append("priorities")
        return missing

    def merged_with(self, updates: dict) -> UserProfile:
        """Return a new profile with ``updates`` applied. Never mutates in place,
        so re-ranking can diff the before and after (section 34)."""
        current = self.model_dump(mode="json", exclude_none=False)
        for key, value in updates.items():
            if value is None:
                continue
            if key == "monthly_spend" and isinstance(value, dict):
                merged = {**current.get("monthly_spend", {}), **value}
                current["monthly_spend"] = merged
            elif key == "priorities" and isinstance(value, dict):
                current["priorities"] = {**current.get("priorities", {}), **value}
                current["priorities_customised"] = True
            else:
                current[key] = value
        return UserProfile.model_validate(current)
