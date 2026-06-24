from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.repositories import DatasetRunRepository, GeneratedFileRepository, IssueManifestRepository, UserRepository, ValidationResultRepository
from backend.app.schemas.api import GenerateRequest
from dataforge.domains import DOMAIN_GENERATORS, DOMAIN_SPECS
from dataforge.exporter import export_run
from dataforge.injector import FailureInjector
from dataforge.modes import build_artifacts, normalize_load_type
from dataforge.validation import reconciliation_report, relationship_report, schema_report, validate

logger = logging.getLogger(__name__)


class DatasetGenerationService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.users = UserRepository(db)
        self.runs = DatasetRunRepository(db)
        self.files = GeneratedFileRepository(db)
        self.issues = IssueManifestRepository(db)
        self.validation_results = ValidationResultRepository(db)

    def generate(self, request: GenerateRequest) -> dict[str, Any]:
        if request.domain not in DOMAIN_SPECS:
            raise ValueError(f"Unsupported domain: {request.domain}")
        spec = DOMAIN_SPECS[request.domain]
        load_type = normalize_load_type(request.load_type)
        if load_type not in {"bulk", "incremental", "delta", "cdc", "event_stream"}:
            raise ValueError(f"Unsupported load type: {request.load_type}")
        started = datetime.now(timezone.utc)
        user = self.users.get_or_create(request.user_email)
        run = self.runs.create(
            user_id=user.id,
            domain=request.domain,
            load_type=load_type,
            file_format=request.format,
            record_count=request.records,
            status="running",
            started_at=started,
        )
        self.db.commit()

        output_dir = get_settings().output_dir / run.id
        try:
            generator = DOMAIN_GENERATORS[request.domain](request.records, 42, load_type, 1)
            clean = generator.generate()
            selected_tables = set(request.selected_tables or spec.schemas)
            invalid_tables = selected_tables.difference(spec.schemas)
            if invalid_tables:
                raise ValueError(f"Unsupported tables for {request.domain}: {sorted(invalid_tables)}")
            issue_rates = {key: self._normalize_issue_rate(value) for key, value in request.issues.items() if value > 0}
            generated, failures = FailureInjector(issue_rates, seed=42, spec=spec).apply(clean, selected_tables) if issue_rates else (clean, [])
            artifacts = build_artifacts(generated, load_type, 42, selected_tables, spec)
            quality = validate(
                generated,
                spec,
                run_id=run.id,
                load_type=load_type,
                file_format=request.format,
                record_count=request.records,
            )
            reports = {
                "quality_report.json": quality,
                "relationship_report.json": relationship_report(generated, spec),
                "schema_report.json": schema_report(generated, spec),
                "reconciliation_report.json": reconciliation_report(generated, spec),
            }
            metadata = {
                "generator": "dataforge-api",
                "version": "0.6.0",
                "domain": request.domain,
                "dataset_name": run.id,
                "run_id": run.id,
                "generated_at": started.isoformat(),
                "seed": 42,
                "requested_records": request.records,
                "selected_tables": sorted(selected_tables),
                "load_type": load_type,
                "output_formats": [request.format],
                "failure_profile": issue_rates or None,
            }
            export_run(output_dir, artifacts, [request.format], metadata, reports, failures)
            exported_metadata = json.loads((output_dir / "metadata.json").read_text(encoding="utf-8"))
            for relative_path, artifact in exported_metadata["artifacts"].items():
                self.files.create(run_id=run.id, path=output_dir / relative_path, file_format=artifact["format"])
            for issue_type, count in self._issue_counts(output_dir).items():
                self.issues.create(run_id=run.id, issue_type=issue_type, issue_count=count, issue_percentage=round(issue_rates.get(issue_type, 0.0) * 100, 3))
            self._persist_validation_results(run.id, quality)
            self.runs.mark_completed(run, datetime.now(timezone.utc))
            self.db.commit()
            logger.info("dataset_generation_completed", extra={"run_id": run.id, "domain": request.domain})
            return {"run_id": run.id, "status": run.status}
        except Exception:
            self.db.rollback()
            run = self.runs.get(run.id)
            if run:
                self.runs.mark_failed(run, datetime.now(timezone.utc))
                self.db.commit()
            logger.exception("dataset_generation_failed", extra={"run_id": run.id if run else None, "domain": request.domain})
            raise

    @staticmethod
    def _issue_counts(output_dir: Path) -> dict[str, int]:
        path = output_dir / "failure_report.json"
        if not path.exists():
            return {}
        payload = json.loads(path.read_text(encoding="utf-8"))
        counts: dict[str, int] = {}
        for event in payload.get("events", []):
            counts[event["failure_type"]] = counts.get(event["failure_type"], 0) + int(event["count"])
        return counts

    @staticmethod
    def _normalize_issue_rate(value: float) -> float:
        return max(0.0, min(float(value), 100.0)) / 100 if value > 1 else max(0.0, min(float(value), 1.0))

    def _persist_validation_results(self, run_id: str, report: dict[str, Any]) -> None:
        quality_score = int(report.get("quality_score", 0))
        for check in report.get("checks", []):
            self.validation_results.create(
                run_id=run_id,
                validation_name=str(check.get("name", check.get("check", "validation"))),
                status=str(check.get("status", "UNKNOWN")),
                quality_score=quality_score,
                expected_value=json.dumps(check.get("expected", check.get("expected_type")), default=str),
                actual_value=json.dumps(check.get("actual", check.get("failures")), default=str),
            )
