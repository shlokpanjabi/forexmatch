"""All ORM models. Importing this package registers every table on ``Base.metadata``."""

from app.db.base import Base
from app.db.models.card import (
    Card,
    CardBenefit,
    CardCurrency,
    CardEligibility,
    CardFee,
    CardLimit,
    FXRateCache,
    Source,
)
from app.db.models.conversation import (
    Message,
    RecommendationRecord,
    Session,
    ToolEvent,
    UserProfileRecord,
)
from app.db.models.verification import VerificationChange, VerificationRun

__all__ = [
    "Base",
    "Card",
    "CardBenefit",
    "CardCurrency",
    "CardEligibility",
    "CardFee",
    "CardLimit",
    "FXRateCache",
    "Source",
    "Message",
    "RecommendationRecord",
    "Session",
    "ToolEvent",
    "UserProfileRecord",
    "VerificationChange",
    "VerificationRun",
]
