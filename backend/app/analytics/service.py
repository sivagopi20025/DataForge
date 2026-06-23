from __future__ import annotations

from sqlalchemy.orm import Session
from sqlalchemy import func, select

from backend.app.models import DatasetRun, ValidationResult
from backend.app.repositories import AdminMetricsRepository, DatasetRunRepository, GeneratedFileRepository, UserRepository, ValidationResultRepository


class AnalyticsService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.runs = DatasetRunRepository(db)
        self.files = GeneratedFileRepository(db)
        self.users = UserRepository(db)
        self.validations = ValidationResultRepository(db)
        self.metrics = AdminMetricsRepository(db)

    def overview(self) -> dict[str, int | float]:
        return {
            "datasets_generated": self.runs.count(),
            "files_generated": self.files.count(),
            "downloads": self.metrics.sum_metric("downloads"),
            "validation_runs": self.validations.count(),
            "average_quality_score": round(self.validations.average_score(), 2),
            "active_users": self.users.count(),
            "daily_active_users": self.users.count(),
            "monthly_active_users": self.users.count(),
        }

    def domains(self) -> dict[str, int]:
        return self.runs.counts_by("domain")

    def formats(self) -> dict[str, int]:
        return self.runs.counts_by("format")

    def load_types(self) -> dict[str, int]:
        return self.runs.counts_by("load_type")

    def quality_by_domain(self) -> dict[str, float]:
        rows = self.db.execute(
            select(DatasetRun.domain, func.avg(ValidationResult.quality_score))
            .join(ValidationResult, ValidationResult.run_id == DatasetRun.id)
            .group_by(DatasetRun.domain)
        ).all()
        return {domain: round(float(score or 0), 2) for domain, score in rows}

    def quality_by_load_type(self) -> dict[str, float]:
        rows = self.db.execute(
            select(DatasetRun.load_type, func.avg(ValidationResult.quality_score))
            .join(ValidationResult, ValidationResult.run_id == DatasetRun.id)
            .group_by(DatasetRun.load_type)
        ).all()
        return {load_type: round(float(score or 0), 2) for load_type, score in rows}

    def quality_trends(self) -> list[dict[str, float | str]]:
        rows = self.db.execute(
            select(func.date(ValidationResult.created_at), func.avg(ValidationResult.quality_score))
            .group_by(func.date(ValidationResult.created_at))
            .order_by(func.date(ValidationResult.created_at))
        ).all()
        return [{"date": str(day), "average_quality_score": round(float(score or 0), 2)} for day, score in rows]

    def ranked_quality_runs(self, *, lowest: bool) -> list[dict[str, str | float]]:
        order = func.avg(ValidationResult.quality_score).asc() if lowest else func.avg(ValidationResult.quality_score).desc()
        rows = self.db.execute(
            select(DatasetRun.id, DatasetRun.domain, DatasetRun.load_type, func.avg(ValidationResult.quality_score))
            .join(ValidationResult, ValidationResult.run_id == DatasetRun.id)
            .group_by(DatasetRun.id, DatasetRun.domain, DatasetRun.load_type)
            .order_by(order)
            .limit(10)
        ).all()
        return [
            {"run_id": run_id, "domain": domain, "load_type": load_type, "quality_score": round(float(score or 0), 2)}
            for run_id, domain, load_type, score in rows
        ]
