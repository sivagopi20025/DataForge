from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base, UUIDTimestampMixin


class DatasetRun(UUIDTimestampMixin, Base):
    __tablename__ = "dataset_runs"

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    domain: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    load_type: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    format: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    record_count: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="dataset_runs")
    generated_files: Mapped[list["GeneratedFile"]] = relationship(back_populates="run", cascade="all, delete-orphan")
    issue_manifests: Mapped[list["IssueManifest"]] = relationship(back_populates="run", cascade="all, delete-orphan")
    validation_results: Mapped[list["ValidationResult"]] = relationship(back_populates="run", cascade="all, delete-orphan")
