"""Conversation state: sessions, messages, profiles, recommendations, tool events.

No user accounts — a client-generated ``session_id`` is the only identity
(BUILD.md section 46). Nothing here stores personal identifiers; the profile
holds only what the comparison needs (section 86).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, uuid_pk
from app.db.models.card import _enum_col
from app.enums import MessageRole, ToolStatus


class Session(Base, TimestampMixin):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = uuid_pk()

    messages: Mapped[list[Message]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="Message.created_at"
    )
    profile: Mapped[UserProfileRecord | None] = relationship(
        back_populates="session", cascade="all, delete-orphan", uselist=False
    )


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (Index("ix_messages_session_id_created_at", "session_id", "created_at"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    session_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[MessageRole] = _enum_col(MessageRole, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=__import__("sqlalchemy").func.now()
    )

    session: Mapped[Session] = relationship(back_populates="messages")


class UserProfileRecord(Base, TimestampMixin):
    """One evolving profile per session, stored as JSON so the Pydantic model
    stays the single definition of shape (BUILD.md section 47)."""

    __tablename__ = "user_profiles"

    id: Mapped[uuid.UUID] = uuid_pk()
    session_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    profile_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    session: Mapped[Session] = relationship(back_populates="profile")


class RecommendationRecord(Base):
    __tablename__ = "recommendations"
    __table_args__ = (Index("ix_recommendations_session_id_created_at", "session_id", "created_at"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    session_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    recommended_card_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("cards.id", ondelete="SET NULL")
    )
    recommendation_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=__import__("sqlalchemy").func.now()
    )


class ToolEvent(Base):
    """An actual agent tool invocation. The UI renders these directly, so they
    must never be synthesised (BUILD.md sections 48, 50, 89)."""

    __tablename__ = "tool_events"
    __table_args__ = (Index("ix_tool_events_session_id_started_at", "session_id", "started_at"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    session_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    tool_name: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[ToolStatus] = _enum_col(ToolStatus, nullable=False)
    #: Short, non-sensitive summaries only (BUILD.md section 48).
    input_summary: Mapped[str | None] = mapped_column(Text)
    output_summary: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
