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
        domain_counts = self.domains()
        format_counts = self.formats()
        load_type_counts = self.load_types()
        return {
            "datasets_generated": self.runs.count(),
            "files_generated": self.files.count(),
            "downloads": self.metrics.sum_metric("downloads"),
            "validation_runs": self.validations.count(),
            "average_quality_score": round(self.validations.average_score(), 2),
            "most_used_domain": self._top_key(domain_counts),
            "most_used_format": self._top_key(format_counts),
            "most_used_load_type": self._top_key(load_type_counts),
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
        run_scores = (
            select(ValidationResult.run_id, func.max(ValidationResult.quality_score).label("quality_score"))
            .where(ValidationResult.quality_score.is_not(None))
            .group_by(ValidationResult.run_id)
            .subquery()
        )
        rows = self.db.execute(
            select(DatasetRun.domain, func.avg(run_scores.c.quality_score))
            .join(run_scores, run_scores.c.run_id == DatasetRun.id)
            .group_by(DatasetRun.domain)
        ).all()
        return {domain: round(float(score or 0), 2) for domain, score in rows}

    def quality_by_load_type(self) -> dict[str, float]:
        run_scores = (
            select(ValidationResult.run_id, func.max(ValidationResult.quality_score).label("quality_score"))
            .where(ValidationResult.quality_score.is_not(None))
            .group_by(ValidationResult.run_id)
            .subquery()
        )
        rows = self.db.execute(
            select(DatasetRun.load_type, func.avg(run_scores.c.quality_score))
            .join(run_scores, run_scores.c.run_id == DatasetRun.id)
            .group_by(DatasetRun.load_type)
        ).all()
        return {load_type: round(float(score or 0), 2) for load_type, score in rows}

    def quality_trends(self) -> list[dict[str, float | str]]:
        run_scores = (
            select(
                ValidationResult.run_id,
                func.date(func.min(ValidationResult.created_at)).label("created_date"),
                func.max(ValidationResult.quality_score).label("quality_score"),
            )
            .where(ValidationResult.quality_score.is_not(None))
            .group_by(ValidationResult.run_id)
            .subquery()
        )
        rows = self.db.execute(
            select(run_scores.c.created_date, func.avg(run_scores.c.quality_score))
            .group_by(run_scores.c.created_date)
            .order_by(run_scores.c.created_date)
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

    @staticmethod
    def _top_key(counts: dict[str, int]) -> str | None:
        if not counts:
            return None
        return max(counts.items(), key=lambda item: item[1])[0]
