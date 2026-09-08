"""Verification pipeline tables.

The first version never writes to the card catalogue automatically: research
produces *proposed* changes that a human approves (BUILD.md sections 42–44).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, uuid_pk
from app.db.models.card import _enum_col
from app.enums import Confidence, VerificationRunStatus, VerificationStatus


class VerificationRun(Base):
    __tablename__ = "verification_runs"

    id: Mapped[uuid.UUID] = uuid_pk()
    card_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("cards.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[VerificationRunStatus] = _enum_col(VerificationRunStatus, nullable=False)
    triggered_by: Mapped[str] = mapped_column(String(60), nullable=False, default="manual")
    sources_checked: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    changes_proposed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    changes: Mapped[list[VerificationChange]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class VerificationChange(Base):
    __tablename__ = "verification_changes"
    __table_args__ = (Index("ix_verification_changes_status", "status"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    run_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("verification_runs.id", ondelete="CASCADE"), nullable=False
    )
    card_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("cards.id", ondelete="CASCADE"), nullable=False
    )
    #: Dotted path to the fact, e.g. "fee.atm_withdrawal.amount".
    field: Mapped[str] = mapped_column(String(200), nullable=False)
    old_value: Mapped[str | None] = mapped_column(Text)
    new_value: Mapped[str | None] = mapped_column(Text)
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("sources.id", ondelete="SET NULL")
    )
    confidence: Mapped[Confidence] = _enum_col(Confidence, nullable=False)
    status: Mapped[VerificationStatus] = _enum_col(
        VerificationStatus, nullable=False, default=VerificationStatus.PENDING
    )
    reviewer_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=__import__("sqlalchemy").func.now()
    )

    run: Mapped[VerificationRun] = relationship(back_populates="changes")
