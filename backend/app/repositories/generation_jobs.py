from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.app.models import GenerationJob


class GenerationJobRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, *, request_payload: dict[str, Any], status: str = "queued") -> GenerationJob:
        job = GenerationJob(status=status, request_payload=json.dumps(request_payload, default=str))
        self.db.add(job)
        self.db.flush()
        return job

    def get(self, job_id: str) -> GenerationJob | None:
        return self.db.scalar(
            select(GenerationJob)
            .where(GenerationJob.id == job_id)
            .options(
                selectinload(GenerationJob.run),
            )
        )

    def mark_running(self, job: GenerationJob, started_at: datetime) -> GenerationJob:
        job.status = "running"
        job.started_at = started_at
        job.error_message = None
        self.db.flush()
        return job

    def mark_completed(self, job: GenerationJob, *, run_id: str, completed_at: datetime) -> GenerationJob:
        job.status = "completed"
        job.run_id = run_id
        job.completed_at = completed_at
        job.error_message = None
        self.db.flush()
        return job

    def mark_failed(self, job: GenerationJob, *, error_message: str, completed_at: datetime) -> GenerationJob:
        job.status = "failed"
        job.error_message = error_message
        job.completed_at = completed_at
        self.db.flush()
        return job
