from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base, utc_now


class AdminMetric(Base):
    __tablename__ = "admin_metrics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    metric_name: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    metric_value: Mapped[float] = mapped_column(Float, nullable=False)
    metric_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
