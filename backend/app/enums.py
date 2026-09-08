"""Domain enumerations shared by the ORM, the Pydantic schemas and the engine.

Kept out of the ORM package so that pure modules (the recommendation engine, the
FX service) can import them without pulling in SQLAlchemy.
"""

from __future__ import annotations

from enum import StrEnum


class CardType(StrEnum):
    PREPAID_FOREX = "prepaid_forex"
    MULTI_CURRENCY_FOREX = "multi_currency_forex"
    SINGLE_CURRENCY_FOREX = "single_currency_forex"
    TRAVEL_DEBIT = "travel_debit"


class CardNetwork(StrEnum):
    VISA = "visa"
    MASTERCARD = "mastercard"
    RUPAY = "rupay"
    MULTIPLE = "multiple"
    UNKNOWN = "unknown"


class FeeType(StrEnum):
    ISSUANCE = "issuance"
    RELOAD = "reload"
    ATM_WITHDRAWAL = "atm_withdrawal"
    CROSS_CURRENCY = "cross_currency"
    REPLACEMENT = "replacement"
    ENCASHMENT = "encashment"
    INACTIVITY = "inactivity"
    BALANCE_ENQUIRY = "balance_enquiry"
    TRANSACTION = "transaction"
    OTHER = "other"


class LimitType(StrEnum):
    DAILY_ATM = "daily_atm"
    DAILY_SPEND = "daily_spend"
    MONTHLY_RELOAD = "monthly_reload"
    ANNUAL_RELOAD = "annual_reload"
    WALLET_LIMIT = "wallet_limit"
    ATM_PER_DAY_COUNT = "atm_per_day_count"


class BenefitType(StrEnum):
    CASHBACK = "cashback"
    DISCOUNT = "discount"
    LOUNGE_ACCESS = "lounge_access"
    INSURANCE = "insurance"
    TRAVEL = "travel"
    EMERGENCY_ASSISTANCE = "emergency_assistance"
    FRAUD_PROTECTION = "fraud_protection"
    CARD_CONTROLS = "card_controls"
    TRANSACTION_ALERTS = "transaction_alerts"
    EMERGENCY_REPLACEMENT = "emergency_replacement"
    ONLINE_MANAGEMENT = "online_management"
    ONLINE_APPLICATION = "online_application"
    ONLINE_RELOAD = "online_reload"
    OTHER = "other"


class EligibilityCriterion(StrEnum):
    MIN_AGE = "min_age"
    RESIDENCY = "residency"
    STUDENT_ONLY = "student_only"
    EXISTING_RELATIONSHIP = "existing_relationship"
    DOCUMENTATION = "documentation"
    PURPOSE = "purpose"
    OTHER = "other"


class SourceType(StrEnum):
    """Ordered by trust — see BUILD.md section 13."""

    OFFICIAL_PRODUCT_PAGE = "official_product_page"
    OFFICIAL_FEE_SCHEDULE = "official_fee_schedule"
    OFFICIAL_TERMS = "official_terms"
    OFFICIAL_FAQ = "official_faq"
    SECONDARY_SOURCE = "secondary_source"


#: Lower rank == more trustworthy. Used when two sources disagree.
SOURCE_TRUST_RANK: dict[SourceType, int] = {
    SourceType.OFFICIAL_PRODUCT_PAGE: 1,
    SourceType.OFFICIAL_FEE_SCHEDULE: 2,
    SourceType.OFFICIAL_TERMS: 3,
    SourceType.OFFICIAL_FAQ: 4,
    SourceType.SECONDARY_SOURCE: 5,
}


class AtmUsage(StrEnum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNKNOWN = "unknown"


class TripType(StrEnum):
    STUDY = "study"
    TOURISM = "tourism"
    BUSINESS = "business"
    OTHER = "other"


class Confidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ValueConfidence(StrEnum):
    """How a numeric profile value was arrived at."""

    STATED = "stated"
    ESTIMATED = "estimated"
    ASSUMED = "assumed"


class Freshness(StrEnum):
    """Age buckets for verified card data — BUILD.md section 56."""

    FRESH = "fresh"          # < 7 days
    RECENT = "recent"        # 7–30 days
    AGING = "aging"          # 30–90 days
    STALE = "stale"          # > 90 days
    UNKNOWN = "unknown"


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ToolStatus(StrEnum):
    STARTED = "started"
    SUCCESS = "success"
    ERROR = "error"


class VerificationStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class VerificationRunStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ScoreComponent(StrEnum):
    COST = "cost"
    ATM = "atm"
    CURRENCY_SUPPORT = "currency_support"
    CONVENIENCE = "convenience"
    REWARDS = "rewards"
    SECURITY = "security"
