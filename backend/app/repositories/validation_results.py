from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.models import ValidationResult


class ValidationResultRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        run_id: str,
        validation_name: str,
        status: str,
        quality_score: int | None = None,
        expected_value: str | None = None,
        actual_value: str | None = None,
    ) -> ValidationResult:
        result = ValidationResult(
            run_id=run_id,
            validation_name=validation_name,
            status=status,
            quality_score=quality_score,
            expected_value=expected_value,
            actual_value=actual_value,
        )
        self.db.add(result)
        self.db.flush()
        return result

    def delete_for_run(self, run_id: str) -> None:
        for row in self.db.scalars(select(ValidationResult).where(ValidationResult.run_id == run_id)):
            self.db.delete(row)
        self.db.flush()

    def count(self) -> int:
        return int(self.db.scalar(select(func.count(ValidationResult.id))) or 0)

    def average_score(self) -> float:
        run_scores = (
            select(ValidationResult.run_id, func.max(ValidationResult.quality_score).label("quality_score"))
            .where(ValidationResult.quality_score.is_not(None))
            .group_by(ValidationResult.run_id)
            .subquery()
        )
        return float(self.db.scalar(select(func.coalesce(func.avg(run_scores.c.quality_score), 0))) or 0)
