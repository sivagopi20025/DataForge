from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base, UUIDTimestampMixin


class EvaluationRun(UUIDTimestampMixin, Base):
    __tablename__ = "evaluation_runs"

    scenario_run_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    benchmark_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    benchmark_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    detector_name: Mapped[str] = mapped_column(String(255), nullable=False)
    detector_version: Mapped[str | None] = mapped_column(String(120), nullable=True)
    detector_output_format: Mapped[str] = mapped_column(String(40), nullable=False, default="json")
    detector_output_checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)
    detector_output_artifact: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    result_artifact: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    metrics_json: Mapped[str] = mapped_column(Text(), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
