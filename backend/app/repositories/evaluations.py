from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import EvaluationRun


class EvaluationRunRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, **values) -> EvaluationRun:
        evaluation = EvaluationRun(**values)
        self.db.add(evaluation)
        self.db.flush()
        return evaluation

    def get(self, evaluation_id: str) -> EvaluationRun | None:
        return self.db.get(EvaluationRun, evaluation_id)

    def list(self, *, limit: int = 50, offset: int = 0) -> list[EvaluationRun]:
        return list(self.db.scalars(select(EvaluationRun).order_by(EvaluationRun.created_at.desc()).limit(limit).offset(offset)))
