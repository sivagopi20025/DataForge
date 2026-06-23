from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base, utc_now


class IssueManifest(Base):
    __tablename__ = "issue_manifests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("dataset_runs.id"), nullable=False, index=True)
    issue_type: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    issue_count: Mapped[int] = mapped_column(Integer, nullable=False)
    issue_percentage: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    run: Mapped["DatasetRun"] = relationship(back_populates="issue_manifests")
