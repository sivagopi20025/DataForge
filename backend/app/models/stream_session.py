from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base, UUIDTimestampMixin


class StreamSession(UUIDTimestampMixin, Base):
    __tablename__ = "stream_sessions"

    domain: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    event_types: Mapped[str] = mapped_column(Text, nullable=False)
    events_per_second: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    format: Mapped[str] = mapped_column(String(20), nullable=False, default="json")
    seed: Mapped[int] = mapped_column(Integer, nullable=False, default=42)
    status: Mapped[str] = mapped_column(String(50), index=True, nullable=False, default="queued")
    failure_injections: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    stream_token_hash: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    stream_token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    webhook_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    webhook_secret_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    webhook_delivery_summary: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    events_generated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    events_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failure_summary: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    estimated_end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    events: Mapped[list["StreamEvent"]] = relationship(back_populates="session", cascade="all, delete-orphan")
