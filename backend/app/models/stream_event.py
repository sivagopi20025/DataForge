from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base, utc_now


class StreamEvent(Base):
    __tablename__ = "stream_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    stream_id: Mapped[str] = mapped_column(String(36), ForeignKey("stream_sessions.id"), index=True, nullable=False)
    event_id: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    domain: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    sequence_number: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ingestion_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    injected_issues: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    raw_event: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_malformed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    session: Mapped["StreamSession"] = relationship(back_populates="events")
