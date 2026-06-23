from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.repositories import DatasetRunRepository, ValidationResultRepository

logger = logging.getLogger(__name__)


class ValidationService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.runs = DatasetRunRepository(db)
        self.results = ValidationResultRepository(db)

    def validate_run(self, run_id: str) -> dict[str, Any]:
        run = self.runs.get(run_id)
        if not run:
            raise ValueError(f"Run not found: {run_id}")
        report_path = get_settings().output_dir / run_id / "quality_report.json"
        if not report_path.exists():
            raise ValueError(f"Validation report not found for run: {run_id}")
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.results.delete_for_run(run_id)
        quality_score = int(report.get("quality_score", 0))
        for check in report.get("checks", []):
            self.results.create(
                run_id=run_id,
                validation_name=str(check.get("name", check.get("check", "validation"))),
                status=str(check.get("status", "UNKNOWN")),
                quality_score=quality_score,
                expected_value=json.dumps(check.get("expected", check.get("expected_type")), default=str),
                actual_value=json.dumps(check.get("actual", check.get("failures")), default=str),
            )
        self.db.commit()
        logger.info("validation_completed", extra={"run_id": run_id})
        return report
