from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from backend.app.models import DatasetRun


class DatasetRunRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        user_id: str,
        domain: str,
        load_type: str,
        file_format: str,
        record_count: int,
        status: str,
        started_at: datetime,
        completed_at: datetime | None = None,
    ) -> DatasetRun:
        run = DatasetRun(
            user_id=user_id,
            domain=domain,
            load_type=load_type,
            format=file_format,
            record_count=record_count,
            status=status,
            started_at=started_at,
            completed_at=completed_at,
        )
        self.db.add(run)
        self.db.flush()
        return run

    def get(self, run_id: str) -> DatasetRun | None:
        return self.db.scalar(
            select(DatasetRun)
            .where(DatasetRun.id == run_id)
            .options(
                selectinload(DatasetRun.generated_files),
                selectinload(DatasetRun.issue_manifests),
                selectinload(DatasetRun.validation_results),
            )
        )

    def list(self, *, limit: int = 50, offset: int = 0) -> list[DatasetRun]:
        return list(
            self.db.scalars(
                select(DatasetRun)
                .order_by(DatasetRun.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
        )

    def count(self) -> int:
        return int(self.db.scalar(select(func.count(DatasetRun.id))) or 0)

    def mark_completed(self, run: DatasetRun, completed_at: datetime, status: str = "completed") -> DatasetRun:
        run.completed_at = completed_at
        run.status = status
        self.db.flush()
        return run

    def mark_failed(self, run: DatasetRun, completed_at: datetime) -> DatasetRun:
        run.completed_at = completed_at
        run.status = "failed"
        self.db.flush()
        return run

    def counts_by(self, column_name: str) -> dict[str, int]:
        column = getattr(DatasetRun, column_name)
        rows = self.db.execute(select(column, func.count(DatasetRun.id)).group_by(column)).all()
        return {str(key): int(value) for key, value in rows}
