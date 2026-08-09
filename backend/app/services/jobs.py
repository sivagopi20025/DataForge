from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from backend.app.db.session import SessionLocal
from backend.app.repositories import GenerationJobRepository
from backend.app.schemas.api import GenerateRequest
from backend.app.services.generation import DatasetGenerationService
from dataforge.domains import DOMAIN_SPECS
from dataforge.modes import normalize_load_type

logger = logging.getLogger(__name__)


class GenerationJobService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.jobs = GenerationJobRepository(db)

    def enqueue(self, payload: GenerateRequest) -> dict[str, Any]:
        self._validate_request(payload)
        job = self.jobs.create(request_payload=payload.model_dump())
        self.db.commit()
        return {"job_id": job.id, "status": job.status, "run_id": job.run_id}

    @staticmethod
    def _validate_request(payload: GenerateRequest) -> None:
        if payload.domain not in DOMAIN_SPECS:
            raise ValueError(f"Unsupported domain: {payload.domain}")
        load_type = normalize_load_type(payload.load_type)
        if load_type not in {"bulk", "incremental", "delta", "cdc", "event_stream"}:
            raise ValueError(f"Unsupported load type: {payload.load_type}")
        selected_tables = set(payload.selected_tables or [])
        invalid_tables = selected_tables.difference(DOMAIN_SPECS[payload.domain].schemas)
        if invalid_tables:
            raise ValueError(f"Unsupported tables for {payload.domain}: {sorted(invalid_tables)}")


def run_generation_job(job_id: str, session_factory: Callable[[], Session] = SessionLocal) -> None:
    db = session_factory()
    jobs = GenerationJobRepository(db)
    try:
        job = jobs.get(job_id)
        if not job:
            logger.error("generation_job_not_found", extra={"job_id": job_id})
            return
        jobs.mark_running(job, datetime.now(timezone.utc))
        db.commit()
        payload = GenerateRequest(**json.loads(job.request_payload))
        result = DatasetGenerationService(db).generate(payload)
        job = jobs.get(job_id)
        if job:
            jobs.mark_completed(job, run_id=result["run_id"], completed_at=datetime.now(timezone.utc))
            db.commit()
        logger.info("generation_job_completed", extra={"job_id": job_id, "run_id": result["run_id"]})
    except Exception as error:
        db.rollback()
        job = jobs.get(job_id)
        if job:
            jobs.mark_failed(job, error_message=str(error), completed_at=datetime.now(timezone.utc))
            db.commit()
        logger.exception("generation_job_failed", extra={"job_id": job_id})
    finally:
        db.close()
