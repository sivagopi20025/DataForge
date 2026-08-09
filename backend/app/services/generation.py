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
from backend.app.services.storage import get_storage_service
from dataforge.canonical import empty_dataset, realism_report
from dataforge.ddl import generate_ddl_package
from dataforge.domains import DOMAIN_GENERATORS, DOMAIN_SPECS
from dataforge.exporter import alignment_report, export_run
from dataforge.injector import FailureInjector
from dataforge.modes import build_artifacts, normalize_load_type
from dataforge.realism import apply_realism
from dataforge.scenarios.builder import execute_failure_plan, get_expanded_scenario
from dataforge.scenarios.configuration import FailurePlan
from dataforge.scenarios.models import ScenarioRunConfig
from dataforge.scenarios.mutations import REFERENCE_SCENARIO_IDS, apply_reference_scenario_mutations
from dataforge.scenarios.registry import get_scenario
from dataforge.scenarios.validators import scenario_outcome_from_validations, validate_scenario_dataset
from dataforge.schema_drift import export_schema_versions
from dataforge.validation import reconciliation_report, relationship_report, schema_report, validate

logger = logging.getLogger(__name__)

MAX_GENERATION_ATTEMPTS = 3
BASE_GENERATION_SEED = 42


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
            selected_tables = set(request.selected_tables or spec.schemas)
            invalid_tables = selected_tables.difference(spec.schemas)
            if invalid_tables:
                raise ValueError(f"Unsupported tables for {request.domain}: {sorted(invalid_tables)}")
            clean, selected_seed, retry_report, realism_engine_report = self._generate_clean_dataset_with_retries(
                request=request,
                load_type=load_type,
                selected_tables=selected_tables,
                run_id=run.id,
            )
            requested_issue_rates = {key: self._normalize_issue_rate(value) for key, value in request.issues.items() if value > 0}
            issue_rates = {} if request.records == 0 else requested_issue_rates
            scenario_mutation_report: dict[str, Any] = {}
            if request.failure_plan and request.scenario_id and request.records > 0:
                scenario = get_expanded_scenario(request.scenario_id)
                failure_plan = FailurePlan.model_validate(request.failure_plan)
                generated, failures, scenario_mutation_report = execute_failure_plan(
                    clean,
                    spec,
                    scenario,
                    failure_plan,
                    severity=(request.scenario_run_config or {}).get("severity", "medium"),
                )
            elif request.scenario_id in REFERENCE_SCENARIO_IDS and issue_rates and request.scenario_run_config:
                scenario = get_scenario(request.scenario_id)
                scenario_config = ScenarioRunConfig(**request.scenario_run_config)
                generated, failures, scenario_mutation_report = apply_reference_scenario_mutations(
                    clean,
                    scenario=scenario,
                    config=scenario_config,
                    spec=spec,
                    seed=selected_seed,
                    rates=issue_rates,
                )
            else:
                generated, failures = FailureInjector(issue_rates, seed=selected_seed, spec=spec).apply(clean, selected_tables) if issue_rates else (clean, [])
            artifacts = build_artifacts(generated, load_type, selected_seed, selected_tables, spec)
            clean_counts = {table: len(rows) for table, rows in clean.items()}
            final_counts = {table: len(rows) for table, rows in generated.items()}
            quality = validate(
                generated,
                spec,
                selected_tables,
                run_id=run.id,
                load_type=load_type,
                file_format=request.format,
                record_count=request.records,
            )
            canonical_realism = realism_report(spec, profile="realistic", requested_records=request.records, actual_counts=final_counts)
            reports = {
                "quality_report.json": quality,
                "relationship_report.json": relationship_report(generated, spec, selected_tables),
                "schema_report.json": schema_report(generated, spec, selected_tables),
                "reconciliation_report.json": reconciliation_report(generated, spec, selected_tables),
                "alignment_report.json": alignment_report(clean_counts=clean_counts, final_counts=final_counts, failures=failures, artifacts=artifacts, spec=spec),
                "realism_report.json": {**canonical_realism, "engine": realism_engine_report},
            }
            if request.scenario_definition:
                reports["scenario_definition.json"] = request.scenario_definition
            if request.scenario_run_config:
                reports["scenario_run_config.json"] = request.scenario_run_config
            if request.expected_validations:
                reports["expected_validations.json"] = request.expected_validations
            if request.scenario_execution_report:
                actual_issue_counts = self._issue_counts_from_events(failures)
                scenario_validator_results = []
                if scenario_mutation_report.get("scenario_validator_results"):
                    scenario_validator_results = scenario_mutation_report["scenario_validator_results"]
                elif request.scenario_id in REFERENCE_SCENARIO_IDS and request.scenario_run_config:
                    scenario = get_scenario(request.scenario_id)
                    scenario_config = ScenarioRunConfig(**request.scenario_run_config)
                    scenario_validator_results = validate_scenario_dataset(
                        generated,
                        scenario=scenario,
                        config=scenario_config,
                        expected_counts=scenario_mutation_report.get("actual_mutation_counts", actual_issue_counts),
                    )
                validator_outcome = scenario_outcome_from_validations(scenario_validator_results) if scenario_validator_results else None
                reports["scenario_execution_report.json"] = {
                    **request.scenario_execution_report,
                    **scenario_mutation_report,
                    "actual_issue_counts": actual_issue_counts,
                    "detected_issue_counts": actual_issue_counts,
                    "scenario_validator_results": scenario_validator_results,
                    "passed_validations": [check.get("name") or check.get("check") for check in quality.get("checks", []) if check.get("status") == "PASS"],
                    "failed_validations": [check.get("name") or check.get("check") for check in quality.get("checks", []) if check.get("status") != "PASS"],
                    "reconciliation_result": "PASS" if validator_outcome == "PASS" else self._scenario_reconciliation_result(scenario_mutation_report, actual_issue_counts, issue_rates),
                    "scenario_outcome": validator_outcome or self._scenario_outcome(scenario_mutation_report, actual_issue_counts, issue_rates, quality),
                    "execution_timing": {**request.scenario_execution_report.get("execution_timing", {}), "generated_at": started.isoformat()},
                }
            if request.records == 0 and requested_issue_rates:
                reports["issue_skip_report.json"] = {
                    "status": "SKIPPED",
                    "reason": "records=0; failure injection skipped because there are no eligible rows.",
                    "requested_issues": requested_issue_rates,
                }
            metadata = {
                "generator": "dataforge-api",
                "version": "0.6.0",
                "domain": request.domain,
                "dataset_name": run.id,
                "run_id": run.id,
                "generated_at": started.isoformat(),
                "seed": selected_seed,
                "generation_attempts": retry_report["attempts"],
                "requested_records": request.records,
                "selected_tables": sorted(selected_tables),
                "load_type": load_type,
                "output_formats": [request.format],
                "database_type": request.database_type,
                "failure_profile": issue_rates or None,
                "requested_failure_profile": requested_issue_rates or None,
                "realism_profile": "realistic",
                "scenario_id": request.scenario_id,
            }
            storage = get_storage_service()
            if request.format == "database":
                package = generate_ddl_package(
                    output_dir=output_dir,
                    domain=request.domain,
                    spec=spec,
                    selected_tables=selected_tables,
                    database_type=request.database_type or "",
                )
                (output_dir / "metadata.json").write_text(json.dumps({**metadata, "artifacts": {package.file_name: {"format": "database", "database_type": package.database_type, "package_type": "ddl"}}}, indent=2), encoding="utf-8")
                for filename, report in reports.items():
                    (output_dir / filename).write_text(json.dumps(report, indent=2), encoding="utf-8")
                (output_dir / "failure_report.json").write_text(json.dumps({"total_injected": sum(event.count for event in failures), "events": [event.__dict__ for event in failures]}, indent=2), encoding="utf-8")
                if retry_report["attempts"] > 1 or retry_report["attempt_history"]:
                    (output_dir / "generation_retry_report.json").write_text(json.dumps(retry_report, indent=2), encoding="utf-8")
                stored_object = storage.save_generated_file(package.path, object_key=f"{run.id}/{package.file_name}")
                self.files.create(run_id=run.id, path=package.path, file_format="database", stored_object=stored_object)
            else:
                export_run(output_dir, artifacts, [request.format], metadata, reports, failures, spec)
                export_schema_versions(output_dir, artifacts, [request.format], spec, failures)
                if retry_report["attempts"] > 1 or retry_report["attempt_history"]:
                    (output_dir / "generation_retry_report.json").write_text(json.dumps(retry_report, indent=2), encoding="utf-8")
                exported_metadata = json.loads((output_dir / "metadata.json").read_text(encoding="utf-8"))
                for relative_path, artifact in exported_metadata["artifacts"].items():
                    source_path = output_dir / relative_path
                    object_key = f"{run.id}/{Path(relative_path).as_posix()}"
                    stored_object = storage.save_generated_file(source_path, object_key=object_key)
                    self.files.create(run_id=run.id, path=source_path, file_format=artifact["format"], stored_object=stored_object)
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

    def _generate_clean_dataset_with_retries(
        self,
        *,
        request: GenerateRequest,
        load_type: str,
        selected_tables: set[str],
        run_id: str,
    ) -> tuple[dict[str, list[dict[str, Any]]], int, dict[str, Any], dict[str, Any]]:
        spec = DOMAIN_SPECS[request.domain]
        if request.records == 0:
            clean = empty_dataset(spec, selected_tables)
            clean, realism_engine_report = apply_realism(clean, spec, profile="realistic", seed=BASE_GENERATION_SEED, selected_tables=selected_tables)
            retry_report = {
                "run_id": run_id,
                "domain": request.domain,
                "load_type": load_type,
                "format": request.format,
                "selected_tables": sorted(selected_tables),
                "max_attempts": 1,
                "attempts": 1,
                "selected_seed": BASE_GENERATION_SEED,
                "status": "PASS",
                "reason": "records=0 generated a valid canonical empty dataset; no retry needed.",
                "attempt_history": [],
            }
            return clean, BASE_GENERATION_SEED, retry_report, realism_engine_report
        attempt_history: list[dict[str, Any]] = []
        last_report: dict[str, Any] | None = None
        last_error: str | None = None
        for attempt in range(1, MAX_GENERATION_ATTEMPTS + 1):
            seed = BASE_GENERATION_SEED + attempt - 1
            try:
                generator = DOMAIN_GENERATORS[request.domain](request.records, seed, load_type, 1)
                clean = generator.generate()
                clean, realism_engine_report = apply_realism(clean, spec, profile="realistic", seed=seed, selected_tables=selected_tables)
                validation_report = validate(
                    clean,
                    spec,
                    selected_tables,
                    run_id=run_id,
                    load_type=load_type,
                    file_format=request.format,
                    record_count=request.records,
                )
                attempt_entry = {
                    "attempt": attempt,
                    "seed": seed,
                    "status": validation_report["status"],
                    "quality_score": validation_report["quality_score"],
                    "summary": validation_report["summary"],
                    "failed_checks": [
                        {
                            "name": check.get("name", check.get("check")),
                            "table": check.get("table"),
                            "column": check.get("column"),
                            "actual": check.get("actual"),
                        }
                        for check in validation_report.get("checks", [])
                        if check.get("status") != "PASS"
                    ],
                }
                attempt_history.append(attempt_entry)
                last_report = validation_report
                if int(validation_report.get("summary", {}).get("failed", 0)) == 0:
                    retry_report = {
                        "run_id": run_id,
                        "domain": request.domain,
                        "load_type": load_type,
                        "format": request.format,
                        "selected_tables": sorted(selected_tables),
                        "max_attempts": MAX_GENERATION_ATTEMPTS,
                        "attempts": attempt,
                        "selected_seed": seed,
                        "status": "PASS",
                        "reason": "Clean generated data matched the domain specification before failure injection.",
                        "attempt_history": attempt_history[:-1],
                    }
                    return clean, seed, retry_report, realism_engine_report
                logger.warning(
                    "clean_generation_validation_failed_retrying",
                    extra={"run_id": run_id, "domain": request.domain, "attempt": attempt, "seed": seed},
                )
            except Exception as error:
                last_error = str(error)
                attempt_history.append({"attempt": attempt, "seed": seed, "status": "ERROR", "error": last_error})
                logger.warning(
                    "clean_generation_attempt_error_retrying",
                    extra={"run_id": run_id, "domain": request.domain, "attempt": attempt, "seed": seed},
                    exc_info=True,
                )

        failure_report = {
            "run_id": run_id,
            "domain": request.domain,
            "load_type": load_type,
            "format": request.format,
            "selected_tables": sorted(selected_tables),
            "max_attempts": MAX_GENERATION_ATTEMPTS,
            "attempts": MAX_GENERATION_ATTEMPTS,
            "status": "FAIL",
            "reason": "Clean generated data did not match the domain specification after retry attempts.",
            "attempt_history": attempt_history,
            "last_error": last_error,
            "last_validation_report": last_report,
        }
        output_dir = get_settings().output_dir / run_id
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "generation_retry_report.json").write_text(json.dumps(failure_report, indent=2, default=str), encoding="utf-8")
        raise RuntimeError(
            f"Generated data failed specification validation after {MAX_GENERATION_ATTEMPTS} attempts. "
            f"See generation_retry_report.json for details."
        )

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
    def _issue_counts_from_events(failures) -> dict[str, int]:
        counts: dict[str, int] = {}
        for event in failures:
            counts[event.failure_type] = counts.get(event.failure_type, 0) + int(event.count)
        return counts

    @staticmethod
    def _scenario_reconciliation_result(scenario_report: dict[str, Any], actual_issue_counts: dict[str, int], issue_rates: dict[str, float]) -> str:
        if not issue_rates:
            return "PASS"
        if not actual_issue_counts:
            return "FAIL"
        reconciliation = scenario_report.get("reconciliation_by_failure", {})
        if reconciliation and all(item.get("status") == "PASS" for item in reconciliation.values()):
            return "PASS"
        return "PARTIAL"

    @staticmethod
    def _scenario_outcome(scenario_report: dict[str, Any], actual_issue_counts: dict[str, int], issue_rates: dict[str, float], quality: dict[str, Any]) -> str:
        if not issue_rates:
            return "PASS"
        if not actual_issue_counts:
            return "FAIL"
        reconciliation = scenario_report.get("reconciliation_by_failure", {})
        reconciled = bool(reconciliation) and all(item.get("status") == "PASS" for item in reconciliation.values())
        validation_failed_as_expected = int(quality.get("summary", {}).get("failed", 0)) > 0
        if reconciled and validation_failed_as_expected:
            return "PASS"
        if reconciled or validation_failed_as_expected:
            return "PARTIAL"
        return "FAIL"

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
                expected_value=json.dumps(
                    {
                        "expected": check.get("expected", check.get("expected_type")),
                        "table": check.get("table"),
                        "column": check.get("column"),
                        "message": check.get("message"),
                    },
                    default=str,
                ),
                actual_value=json.dumps(
                    {
                        "actual": check.get("actual", check.get("failures")),
                        "failures": check.get("failures"),
                    },
                    default=str,
                ),
            )
