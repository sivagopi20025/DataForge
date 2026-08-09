from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base, UUIDTimestampMixin


class BenchmarkRun(UUIDTimestampMixin, Base):
    __tablename__ = "benchmark_runs"

    benchmark_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    benchmark_version: Mapped[str] = mapped_column(String(40), nullable=False)
    domain: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    scenario_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    scenario_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    generation_job_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    evaluation_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    status_reason: Mapped[str | None] = mapped_column(Text(), nullable=True)
    detector_mode: Mapped[str] = mapped_column(String(60), nullable=False, default="manual_upload")
    detector_status: Mapped[str] = mapped_column(String(60), nullable=False, default="not_submitted")
    detector_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    detector_version: Mapped[str | None] = mapped_column(String(120), nullable=True)
    detector_output_artifact: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    artifact_manifest_json: Mapped[str] = mapped_column(Text(), nullable=False, default="{}")
    snapshot_json: Mapped[str] = mapped_column(Text(), nullable=False)
    metrics_json: Mapped[str | None] = mapped_column(Text(), nullable=True)
    acceptance_json: Mapped[str | None] = mapped_column(Text(), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    request_fingerprint: Mapped[str | None] = mapped_column(String(128), nullable=True)
    result: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    retain_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
