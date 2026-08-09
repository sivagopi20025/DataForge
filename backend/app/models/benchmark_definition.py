from __future__ import annotations

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base, UUIDTimestampMixin


class BenchmarkDefinition(UUIDTimestampMixin, Base):
    __tablename__ = "benchmark_definitions"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(40), nullable=False, default="v1")
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    domain: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    scenario_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    scenario_template_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    records: Mapped[int] = mapped_column(Integer, nullable=False, default=10_000)
    output_format: Mapped[str] = mapped_column(String(40), nullable=False, default="csv")
    seed: Mapped[int] = mapped_column(Integer, nullable=False, default=42)
    failure_plan_json: Mapped[str] = mapped_column(Text(), nullable=False)
    evaluation_unit: Mapped[str] = mapped_column(String(80), nullable=False, default="entity")
    thresholds_json: Mapped[str] = mapped_column(Text(), nullable=False, default="{}")
    snapshot_json: Mapped[str] = mapped_column(Text(), nullable=False, default="{}")
