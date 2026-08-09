from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base, UUIDTimestampMixin


class ScenarioTemplate(UUIDTimestampMixin, Base):
    __tablename__ = "scenario_templates"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    domain: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    scenario_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    records: Mapped[int] = mapped_column(Integer, nullable=False, default=10_000)
    output_format: Mapped[str] = mapped_column(String(40), nullable=False, default="csv")
    severity: Mapped[str] = mapped_column(String(40), nullable=False, default="medium")
    seed_behavior: Mapped[str] = mapped_column(String(40), nullable=False, default="fixed_seed")
    failure_plan_json: Mapped[str] = mapped_column(Text(), nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
