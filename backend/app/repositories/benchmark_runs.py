from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.models import BenchmarkRun


class BenchmarkRunRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, **values) -> BenchmarkRun:
        run = BenchmarkRun(**values)
        self.db.add(run)
        self.db.flush()
        return run

    def get(self, benchmark_run_id: str) -> BenchmarkRun | None:
        return self.db.get(BenchmarkRun, benchmark_run_id)

    def get_by_idempotency_key(self, key: str) -> BenchmarkRun | None:
        return self.db.scalar(select(BenchmarkRun).where(BenchmarkRun.idempotency_key == key).order_by(BenchmarkRun.created_at.desc()))

    def count_active(self) -> int:
        active_statuses = {"queued", "generating", "detector_received", "evaluating", "cancellation_requested"}
        return int(self.db.scalar(select(func.count(BenchmarkRun.id)).where(BenchmarkRun.status.in_(active_statuses))) or 0)

    def list(
        self,
        *,
        benchmark_id: str | None = None,
        status: str | None = None,
        domain: str | None = None,
        scenario_id: str | None = None,
        result: str | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[BenchmarkRun]:
        statement = select(BenchmarkRun).order_by(BenchmarkRun.created_at.desc())
        if benchmark_id:
            statement = statement.where(BenchmarkRun.benchmark_id == benchmark_id)
        if status:
            statement = statement.where(BenchmarkRun.status == status)
        if domain:
            statement = statement.where(BenchmarkRun.domain == domain)
        if scenario_id:
            statement = statement.where(BenchmarkRun.scenario_id == scenario_id)
        if result:
            statement = statement.where(BenchmarkRun.result == result)
        if created_from:
            statement = statement.where(BenchmarkRun.created_at >= created_from)
        if created_to:
            statement = statement.where(BenchmarkRun.created_at <= created_to)
        return list(self.db.scalars(statement.limit(limit).offset(offset)))
