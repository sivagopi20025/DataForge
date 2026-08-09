from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import BenchmarkDefinition


class BenchmarkDefinitionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, **values) -> BenchmarkDefinition:
        benchmark = BenchmarkDefinition(**values)
        self.db.add(benchmark)
        self.db.flush()
        return benchmark

    def get(self, benchmark_id: str) -> BenchmarkDefinition | None:
        return self.db.get(BenchmarkDefinition, benchmark_id)

    def list(self, *, limit: int = 50, offset: int = 0) -> list[BenchmarkDefinition]:
        return list(self.db.scalars(select(BenchmarkDefinition).order_by(BenchmarkDefinition.updated_at.desc()).limit(limit).offset(offset)))
