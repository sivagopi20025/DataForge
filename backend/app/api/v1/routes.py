from __future__ import annotations

import tempfile
import zipfile
import csv
import hashlib
import json
import logging
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Header, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse, Response, StreamingResponse
from starlette.background import BackgroundTask
from sqlalchemy import update
from sqlalchemy.orm import Session

from backend.app.analytics import AnalyticsService
from backend.app.core.config import get_settings
from backend.app.core.rate_limit import enforce_rate_limit
from backend.app.core.rate_limit import rate_limiter
from backend.app.core.security import require_api_key
from backend.app.db.session import get_db
from backend.app.models import GenerationJob
from backend.app.repositories import (
    BenchmarkDefinitionRepository,
    BenchmarkRunRepository,
    DatasetRunRepository,
    EvaluationRunRepository,
    GeneratedFileRepository,
    GenerationJobRepository,
    ScenarioTemplateRepository,
)
from backend.app.schemas.api import (
    BenchmarkCreateRequest,
    BenchmarkRunRequest,
    BenchmarkRunDetectorSubmissionRequest,
    DeleteRunsRequest,
    DeleteRunsResponse,
    EvaluationCreateRequest,
    EvaluationImportRequest,
    GenerateRequest,
    GenerateResponse,
    JobStatusResponse,
    PaginatedRuns,
    RunDetail,
    RunSummary,
    ScenarioConfigRequest,
    ScenarioBuilderGenerateRequest,
    ScenarioRunCompareRequest,
    ScenarioTemplateCreateRequest,
    ScenarioTemplateUpdateRequest,
    StreamEventsResponse,
    StreamStartRequest,
    StreamStartResponse,
    StreamStatusResponse,
    ValidateRequest,
)
from backend.app.services.file_preview import preview_generated_file
from backend.app.services.jobs import GenerationJobService, run_generation_job
from backend.app.services.retention import cleanup_expired_run_history
from backend.app.services.storage import LocalStorageService, get_storage_service
from backend.app.services.streaming import StreamSessionService, run_stream_session, stream_validation_report
from backend.app.services.streaming import STREAM_EVENT_TYPES
from dataforge.domains import DOMAIN_SPECS
from dataforge.scenarios.builder import build_scenario_configuration, compare_scenario_runs, get_expanded_scenario, preview_failure_plan, primitive_display_name, summarize_ground_truth, validate_template_compatibility
from dataforge.scenarios.benchmarking import (
    acceptance_status,
    checksum_bytes,
    dataset_manifest,
    detector_payload_from_csv,
    detector_payload_from_jsonl,
    evaluate_detector_output,
    ground_truth_from_scenario_report,
    ground_truth_to_csv,
    ground_truth_to_jsonl,
    normalize_detector_output,
)
from dataforge.scenarios.catalog import expanded_scenario_items, load_scenario_quality_summary
from dataforge.scenarios.configuration import FailurePlan
from dataforge.scenarios.executor import build_generation_payload
from dataforge.scenarios.matcher import match_scenarios
from dataforge.scenarios.models import ScenarioRunConfig
from dataforge.scenarios.primitives import PRIMITIVE_REGISTRY
from dataforge.scenarios.registry import all_scenarios, find_scenarios, get_scenario, scenario_summary
from dataforge.scenarios.requirements import REQUIREMENT_RESOLVER
from dataforge.scenarios.schema_semantics import COLUMN_SEMANTIC_RESOLVER
from dataforge.scenarios.validator import resolve_config
from dataforge.scenarios.validator_registry import VALIDATOR_REGISTRY
from backend.app.services.validation import ValidationService

router = APIRouter(prefix="/api/v1")
logger = logging.getLogger(__name__)


@router.post("/generate", response_model=GenerateResponse, dependencies=[Depends(require_api_key)])
def generate_dataset(
    payload: GenerateRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, str | None]:
    response = GenerationJobService(db).enqueue(payload)
    background_tasks.add_task(run_generation_job, response["job_id"], request.app.state.SessionLocal)
    return response


@router.get("/catalog/tables/{domain}")
def catalog_tables(domain: str) -> dict:
    if domain not in DOMAIN_SPECS:
        raise ValueError(f"Unsupported domain: {domain}")
    spec = DOMAIN_SPECS[domain]
    return {
        "domain": domain,
        "tables": [
            {
                "name": table_name,
                "primary_key": schema.primary_key,
                "columns": list(schema.columns),
                "foreign_keys": [
                    {
                        "column": foreign_key.column,
                        "references_table": foreign_key.parent_table,
                        "references_column": foreign_key.parent_column,
                    }
                    for foreign_key in schema.foreign_keys
                ],
            }
            for table_name, schema in spec.schemas.items()
        ],
    }


@router.get("/scenarios")
def list_scenarios(
    domain: str | None = None,
    category: str | None = None,
    mode: str | None = None,
    profile: str | None = None,
    severity: str | None = None,
    tag: str | None = None,
    keyword: str | None = None,
) -> dict:
    scenarios = find_scenarios(domain=domain, category=category, mode=mode, profile=profile, severity=severity, tag=tag, keyword=keyword)
    return {"total": len(scenarios), "items": [scenario_summary(scenario) for scenario in scenarios]}


@router.get("/scenarios/search")
def search_scenarios(q: str = Query(default=""), limit: int = Query(default=10, ge=1, le=50)) -> dict:
    items = match_scenarios(q, limit=limit)
    return {"query": q, "total": len(items), "items": items}


@router.get("/scenario-library/summary")
def scenario_library_summary() -> dict:
    items = expanded_scenario_items()
    execution_counts = Counter(item.execution_status for item in items)
    readiness_counts = Counter(item.implementation_readiness for item in items)
    tier_counts = Counter(item.score.tier for item in items if item.score)
    executable_by_domain = Counter(item.domain for item in items if item.execution_status in {"executable", "custom_reference"})
    blocked_by_capability: Counter[str] = Counter()
    blocked_by_schema_type: Counter[str] = Counter()
    blocked_by_dependency_category: Counter[str] = Counter()
    for item in items:
        if item.execution_status != "specification_only":
            continue
        if item.implementation_dependencies.tables:
            blocked_by_schema_type["missing_table"] += 1
            blocked_by_dependency_category["missing_table"] += 1
        if item.implementation_dependencies.columns:
            blocked_by_schema_type["missing_column"] += 1
            blocked_by_dependency_category["missing_column"] += 1
        if item.implementation_dependencies.primitives or item.implementation_dependencies.validators:
            blocked_by_dependency_category["missing_runtime_capability"] += 1
        if item.implementation_dependencies.custom_logic:
            blocked_by_dependency_category["requires_custom_domain_rule"] += 1
        if item.failure_primitive in {"distribution_shift", "schema_change", "identity_mismatch", "rare_high_value_activity"}:
            blocked_by_dependency_category["intentionally_deferred_low_value"] += 1
        if not item.implementation_dependencies.has_dependencies:
            blocked_by_dependency_category["requires_multi_primitive_composition"] += 1
        for table in item.implementation_dependencies.tables:
            blocked_by_capability[f"table:{table}"] += 1
        for column in item.implementation_dependencies.columns:
            blocked_by_capability[f"column:{column}"] += 1
        for primitive in item.implementation_dependencies.primitives:
            blocked_by_capability[f"primitive:{primitive}"] += 1
        for validator in item.implementation_dependencies.validators:
            blocked_by_capability[f"validator:{validator}"] += 1
        for parameter in item.implementation_dependencies.unsupported_parameters:
            blocked_by_capability[f"parameter:{parameter}"] += 1
    return {
        "total_registered": len(items),
        "total_rejected": 36,
        "runtime_registry_count": len(all_scenarios()),
        "total_executable": execution_counts.get("executable", 0),
        "total_custom_reference": execution_counts.get("custom_reference", 0),
        "total_runtime_capable": execution_counts.get("executable", 0) + execution_counts.get("custom_reference", 0),
        "total_specification_only": execution_counts.get("specification_only", 0),
        "execution_status_counts": dict(sorted(execution_counts.items())),
        "implementation_readiness_counts": dict(sorted(readiness_counts.items())),
        "tier_counts": dict(sorted(tier_counts.items())),
        "executable_by_domain": dict(sorted(executable_by_domain.items())),
        "blocked_by_capability": dict(blocked_by_capability.most_common(25)),
        "blocked_by_schema_type": dict(sorted(blocked_by_schema_type.items())),
        "blocked_by_dependency_category": dict(sorted(blocked_by_dependency_category.items())),
        "primitive_registry": {
            "runtime_implemented": sorted(PRIMITIVE_REGISTRY.runtime_implemented()),
            "metadata_only": sorted(PRIMITIVE_REGISTRY.metadata_only()),
        },
        "validator_registry": {
            "runtime_implemented": sorted(VALIDATOR_REGISTRY.runtime_implemented()),
            "metadata_only": sorted(VALIDATOR_REGISTRY.metadata_only()),
        },
    }


@router.get("/scenario-library/quality-summary")
def scenario_library_quality_summary() -> dict:
    return load_scenario_quality_summary()


@router.get("/scenario-library/scenarios/{scenario_id}/configuration")
def scenario_builder_configuration(scenario_id: str, records: int = Query(default=10_000, ge=0)) -> dict:
    return build_scenario_configuration(scenario_id, records=records)


@router.post("/scenario-library/failure-plan/preview", dependencies=[Depends(require_api_key)])
def scenario_failure_plan_preview(payload: dict) -> dict:
    scenario_id = str(payload.get("scenario_id") or "")
    records = int(payload.get("records", 10_000))
    plan_payload = payload.get("failure_plan") or payload
    plan = FailurePlan.model_validate(plan_payload)
    return preview_failure_plan(scenario_id, plan, records=records)


@router.post("/scenario-library/generate", response_model=GenerateResponse, dependencies=[Depends(require_api_key)])
def generate_scenario_builder_dataset(
    payload: ScenarioBuilderGenerateRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, str | None]:
    scenario = get_expanded_scenario(payload.scenario_id)
    plan = FailurePlan.model_validate(payload.failure_plan)
    preview = preview_failure_plan(payload.scenario_id, plan, records=payload.records)
    if not preview["valid"]:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"errors": preview["errors"]})
    selected_tables = [row["table"] for row in build_scenario_configuration(payload.scenario_id, records=payload.records)["required_tables"]]
    generation_payload = GenerateRequest(
        domain=scenario.domain,
        load_type="bulk",
        format=payload.output_format,
        records=payload.records,
        selected_tables=selected_tables,
        issues={},
        user_email=payload.requested_by,
        scenario_id=scenario.scenario_id,
        scenario_run_config={
            "scenario_id": scenario.scenario_id,
            "domain": scenario.domain,
            "mode": "batch",
            "records": payload.records,
            "output_format": payload.output_format,
            "seed": payload.seed,
            "severity": payload.severity,
            "failure_plan": plan.model_dump(by_alias=True),
        },
        scenario_definition=scenario.model_dump(),
        expected_validations={
            "scenario_id": scenario.scenario_id,
            "validator_pattern": scenario.validator_pattern,
            "expected_quality_status": "FAIL",
        },
        scenario_execution_report={
            "scenario_id": scenario.scenario_id,
            "scenario_version": scenario.version,
            "configuration": {"records": payload.records, "output_format": payload.output_format, "seed": payload.seed, "severity": payload.severity},
            "generation_plan_preview": preview,
            "ground_truth_contract": "ground_truth_contract.yaml",
            "reconciliation_result": "PENDING",
            "scenario_outcome": "PENDING",
            "warnings": preview.get("warnings", []),
        },
        failure_plan=plan.model_dump(by_alias=True),
    )
    response = GenerationJobService(db).enqueue(generation_payload)
    background_tasks.add_task(run_generation_job, response["job_id"], request.app.state.SessionLocal)
    return response


@router.get("/scenario-library/templates", dependencies=[Depends(require_api_key)])
def list_scenario_templates(limit: int = Query(default=100, ge=1, le=200), offset: int = Query(default=0, ge=0), db: Session = Depends(get_db)) -> dict:
    repo = ScenarioTemplateRepository(db)
    items = [_template_payload(template) for template in repo.list(limit=limit, offset=offset)]
    return {"total": len(items), "items": items}


@router.post("/scenario-library/templates", dependencies=[Depends(require_api_key)])
def create_scenario_template(payload: ScenarioTemplateCreateRequest, db: Session = Depends(get_db)) -> dict:
    scenario = get_expanded_scenario(payload.scenario_id)
    failure_plan = FailurePlan.model_validate(payload.failure_plan)
    compatibility = validate_template_compatibility({"scenario_id": payload.scenario_id, "failure_plan": failure_plan.model_dump(by_alias=True)})
    if not compatibility["valid"]:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"errors": compatibility["errors"]})
    template = ScenarioTemplateRepository(db).create(
        name=payload.name,
        description=payload.description,
        domain=scenario.domain,
        scenario_id=scenario.scenario_id,
        records=payload.records,
        output_format=payload.output_format,
        severity=payload.severity,
        seed_behavior=payload.seed_behavior,
        failure_plan_json=json.dumps(failure_plan.model_dump(by_alias=True), default=str),
    )
    db.commit()
    return _template_payload(template)


@router.get("/scenario-library/templates/{template_id}", dependencies=[Depends(require_api_key)])
def get_scenario_template(template_id: str, db: Session = Depends(get_db)) -> dict:
    template = ScenarioTemplateRepository(db).get(template_id)
    if not template:
        raise ValueError(f"Scenario template not found: {template_id}")
    return _template_payload(template)


@router.patch("/scenario-library/templates/{template_id}", dependencies=[Depends(require_api_key)])
def update_scenario_template(template_id: str, payload: ScenarioTemplateUpdateRequest, db: Session = Depends(get_db)) -> dict:
    repo = ScenarioTemplateRepository(db)
    template = repo.get(template_id)
    if not template:
        raise ValueError(f"Scenario template not found: {template_id}")
    updates = payload.model_dump(exclude_unset=True)
    failure_plan = updates.pop("failure_plan", None)
    if failure_plan is not None:
        plan = FailurePlan.model_validate(failure_plan)
        compatibility = validate_template_compatibility({"scenario_id": template.scenario_id, "failure_plan": plan.model_dump(by_alias=True)})
        if not compatibility["valid"]:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"errors": compatibility["errors"]})
        updates["failure_plan_json"] = json.dumps(plan.model_dump(by_alias=True), default=str)
    template = repo.update(template, **updates)
    db.commit()
    return _template_payload(template)


@router.delete("/scenario-library/templates/{template_id}", dependencies=[Depends(require_api_key)])
def delete_scenario_template(template_id: str, db: Session = Depends(get_db)) -> dict:
    repo = ScenarioTemplateRepository(db)
    template = repo.get(template_id)
    if not template:
        raise ValueError(f"Scenario template not found: {template_id}")
    repo.delete(template)
    db.commit()
    return {"deleted": True, "template_id": template_id}


@router.post("/scenario-library/templates/{template_id}/prepare-run", dependencies=[Depends(require_api_key)])
def prepare_template_run(template_id: str, db: Session = Depends(get_db)) -> dict:
    repo = ScenarioTemplateRepository(db)
    template = repo.get(template_id)
    if not template:
        raise ValueError(f"Scenario template not found: {template_id}")
    repo.mark_used(template, datetime.now(timezone.utc))
    db.commit()
    payload = _template_payload(template)
    plan = payload["failure_plan"]
    if template.seed_behavior == "new_seed_each_run":
        plan["seed"] = int(datetime.now(timezone.utc).timestamp())
    return {
        "status": "READY" if payload["compatibility"]["valid"] else "NEEDS_UPDATE",
        "template": payload,
        "generation_request": {
            "scenario_id": template.scenario_id,
            "records": template.records,
            "output_format": template.output_format,
            "seed": plan.get("seed", 42),
            "severity": template.severity,
            "failure_plan": plan,
        },
    }


@router.get("/scenario-library/runs", dependencies=[Depends(require_api_key)])
def list_scenario_builder_runs(limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0), db: Session = Depends(get_db)) -> dict:
    runs = DatasetRunRepository(db).list(limit=limit, offset=offset)
    items = [_scenario_builder_run_summary(run) for run in runs if _scenario_reports_for_run(run.id).get("scenario_execution_report.json", {}).get("ground_truth") is not None]
    return {"total": len(items), "items": items}


@router.get("/scenario-library/runs/{run_id}", dependencies=[Depends(require_api_key)])
def scenario_builder_run_detail(run_id: str, db: Session = Depends(get_db)) -> dict:
    run = DatasetRunRepository(db).get(run_id)
    if not run:
        raise ValueError(f"Run not found: {run_id}")
    return _scenario_builder_run_summary(run) | {"reports": _scenario_reports_for_run(run.id)}


@router.post("/scenario-library/runs/{run_id}/prepare-rerun", dependencies=[Depends(require_api_key)])
def prepare_scenario_rerun(run_id: str, db: Session = Depends(get_db)) -> dict:
    run = DatasetRunRepository(db).get(run_id)
    if not run:
        raise ValueError(f"Run not found: {run_id}")
    reports = _scenario_reports_for_run(run.id)
    execution = reports.get("scenario_execution_report.json", {})
    config = reports.get("scenario_run_config.json", {})
    failure_plan = execution.get("failure_plan") or config.get("failure_plan")
    if not failure_plan:
        raise ValueError("Run does not contain a Scenario Builder failure plan snapshot")
    return {
        "status": "READY",
        "run_id": run.id,
        "generation_request": {
            "scenario_id": execution.get("scenario_id") or config.get("scenario_id"),
            "records": config.get("records", run.record_count),
            "output_format": config.get("output_format", run.format),
            "seed": failure_plan.get("seed", config.get("seed", 42)),
            "severity": config.get("severity", "medium"),
            "failure_plan": failure_plan,
        },
    }


@router.post("/scenario-library/runs/compare", dependencies=[Depends(require_api_key)])
def compare_builder_runs(payload: ScenarioRunCompareRequest, db: Session = Depends(get_db)) -> dict:
    left = DatasetRunRepository(db).get(payload.left_run_id)
    right = DatasetRunRepository(db).get(payload.right_run_id)
    if not left or not right:
        raise ValueError("Both run ids must exist")
    left_report = _scenario_reports_for_run(left.id).get("scenario_execution_report.json", {})
    right_report = _scenario_reports_for_run(right.id).get("scenario_execution_report.json", {})
    return {"left_run_id": left.id, "right_run_id": right.id, "comparison": compare_scenario_runs(left_report, right_report)}


@router.get("/scenario-library/runs/{run_id}/ground-truth", response_model=None, dependencies=[Depends(require_api_key)])
def export_scenario_ground_truth(run_id: str, format: str = Query(default="json", pattern="^(json|jsonl|csv)$"), db: Session = Depends(get_db)):
    run = DatasetRunRepository(db).get(run_id)
    if not run:
        raise ValueError(f"Run not found: {run_id}")
    ground_truth = _ground_truth_payload_for_run(run)
    if format == "json":
        return ground_truth
    if format == "jsonl":
        payload = ground_truth_to_jsonl(ground_truth)
        return Response(
            content=payload,
            media_type="application/x-ndjson",
            headers={"Content-Disposition": f'attachment; filename="dataforge-{run_id}-ground-truth.jsonl"'},
        )
    payload = ground_truth_to_csv(ground_truth)
    return Response(
        content=payload,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="dataforge-{run_id}-ground-truth.csv"'},
    )


@router.get("/scenario-library/runs/{run_id}/manifest", dependencies=[Depends(require_api_key)])
def export_scenario_dataset_manifest(run_id: str, db: Session = Depends(get_db)) -> dict:
    run = DatasetRunRepository(db).get(run_id)
    if not run:
        raise ValueError(f"Run not found: {run_id}")
    return _dataset_manifest_for_run(run)


@router.get("/evaluations/detector-contract", dependencies=[Depends(require_api_key)])
def detector_output_contract() -> dict:
    return {
        "detector_output_version": "1.0",
        "supported_formats": ["json", "jsonl", "csv", "api"],
        "json_contract": {
            "detector_name": "my-detector",
            "detector_version": "1.2.3",
            "detections": [
                {
                    "evaluation_unit": "entity",
                    "evaluation_key": {"payment_id": "PAY123"},
                    "predicted_failure": True,
                    "predicted_failure_type": "duplicate_payment",
                    "confidence": 0.98,
                }
            ],
        },
        "csv_columns": ["evaluation_unit", "key_<primary_key_column>", "predicted_failure", "predicted_failure_type", "confidence"],
        "label_mapping": {"duplicate_payment": "duplication"},
        "notes": [
            "evaluation_key must match a ground-truth evaluation key for TP/FN scoring.",
            "Unknown detections are reported separately so bad joins do not silently inflate false positives.",
            "Use ground-truth export and dataset manifest endpoints to build reproducible customer detector tests.",
        ],
    }


@router.post("/evaluations", dependencies=[Depends(require_api_key)])
def create_evaluation(payload: EvaluationCreateRequest, db: Session = Depends(get_db)) -> dict:
    benchmark = BenchmarkDefinitionRepository(db).get(payload.benchmark_id) if payload.benchmark_id else None
    if payload.benchmark_id and not benchmark:
        raise ValueError(f"Benchmark not found: {payload.benchmark_id}")
    return _create_evaluation_result(
        db,
        run_id=payload.run_id,
        detector_name=payload.detector_name,
        detector_version=payload.detector_version,
        detector_output_format=payload.detector_output_format,
        detections=payload.detections,
        label_mapping=payload.label_mapping,
        benchmark=benchmark,
    )


@router.post("/evaluations/import", dependencies=[Depends(require_api_key)])
def import_evaluation(payload: EvaluationImportRequest, db: Session = Depends(get_db)) -> dict:
    benchmark = BenchmarkDefinitionRepository(db).get(payload.benchmark_id) if payload.benchmark_id else None
    if payload.benchmark_id and not benchmark:
        raise ValueError(f"Benchmark not found: {payload.benchmark_id}")
    detector_payload = _parse_detector_payload(payload.detector_output_format, payload.payload)
    return _create_evaluation_result(
        db,
        run_id=payload.run_id,
        detector_name=payload.detector_name or detector_payload.get("detector_name", "imported-detector"),
        detector_version=payload.detector_version or detector_payload.get("detector_version"),
        detector_output_format=payload.detector_output_format,
        detections=detector_payload.get("detections", []),
        label_mapping=payload.label_mapping,
        benchmark=benchmark,
    )


@router.get("/evaluations", dependencies=[Depends(require_api_key)])
def list_evaluations(limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0), db: Session = Depends(get_db)) -> dict:
    repo = EvaluationRunRepository(db)
    items = [_evaluation_payload(item) for item in repo.list(limit=limit, offset=offset)]
    return {"total": len(items), "items": items}


@router.get("/evaluations/{evaluation_id}", dependencies=[Depends(require_api_key)])
def get_evaluation(evaluation_id: str, db: Session = Depends(get_db)) -> dict:
    evaluation = EvaluationRunRepository(db).get(evaluation_id)
    if not evaluation:
        raise ValueError(f"Evaluation not found: {evaluation_id}")
    return _evaluation_payload(evaluation)


@router.get("/benchmarks", dependencies=[Depends(require_api_key)])
def list_benchmarks(limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0), db: Session = Depends(get_db)) -> dict:
    repo = BenchmarkDefinitionRepository(db)
    items = [_benchmark_payload(item) for item in repo.list(limit=limit, offset=offset)]
    return {"total": len(items), "items": items}


@router.post("/benchmarks", dependencies=[Depends(require_api_key)])
def create_benchmark(payload: BenchmarkCreateRequest, db: Session = Depends(get_db)) -> dict:
    scenario = get_expanded_scenario(payload.scenario_id)
    if scenario.domain != payload.domain:
        raise ValueError(f"Scenario {payload.scenario_id} belongs to domain {scenario.domain}, not {payload.domain}")
    benchmark = BenchmarkDefinitionRepository(db).create(
        name=payload.name,
        slug=_slugify(payload.name),
        version="v1",
        description=payload.description,
        domain=payload.domain,
        scenario_id=payload.scenario_id,
        scenario_template_id=payload.scenario_template_id,
        records=payload.records,
        output_format=payload.output_format,
        seed=payload.seed,
        failure_plan_json=json.dumps(payload.failure_plan, default=str),
        evaluation_unit=payload.evaluation_unit,
        thresholds_json=json.dumps(payload.thresholds, default=str),
        snapshot_json=json.dumps({"scenario": scenario.model_dump(), "created_from": "api"}, default=str),
    )
    db.commit()
    return _benchmark_payload(benchmark)


@router.get("/benchmarks/{benchmark_id}", dependencies=[Depends(require_api_key)])
def get_benchmark(benchmark_id: str, db: Session = Depends(get_db)) -> dict:
    benchmark = BenchmarkDefinitionRepository(db).get(benchmark_id)
    if not benchmark:
        raise ValueError(f"Benchmark not found: {benchmark_id}")
    return _benchmark_payload(benchmark)


@router.post("/benchmarks/{benchmark_id}/runs", dependencies=[Depends(require_api_key)])
def run_benchmark(
    benchmark_id: str,
    payload: BenchmarkRunRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
) -> dict:
    benchmark = BenchmarkDefinitionRepository(db).get(benchmark_id)
    if not benchmark:
        raise ValueError(f"Benchmark not found: {benchmark_id}")
    if payload.run_id:
        if not payload.detector_name:
            raise ValueError("detector_name is required when evaluating an existing scenario run")
        return _create_evaluation_result(
            db,
            run_id=payload.run_id,
            detector_name=payload.detector_name,
            detector_version=payload.detector_version,
            detector_output_format=payload.detector_output_format,
            detections=payload.detections,
            label_mapping=payload.label_mapping,
            benchmark=benchmark,
        )
    _enforce_benchmark_quota(request, idempotency_key)
    run, created = _create_benchmark_run(db, benchmark, payload, idempotency_key=idempotency_key)
    db.commit()
    if created:
        background_tasks.add_task(_execute_benchmark_run, run.id, request.app.state.SessionLocal)
        logger.info("benchmark_run_created", extra={"benchmark_run_id": run.id, "benchmark_id": benchmark.id})
    return {"benchmark_run_id": run.id, "status": run.status}


@router.get("/benchmark-runs", dependencies=[Depends(require_api_key)])
def list_benchmark_runs(
    benchmark_id: str | None = None,
    status: str | None = None,
    domain: str | None = None,
    scenario_id: str | None = None,
    result: str | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> dict:
    runs = BenchmarkRunRepository(db).list(
        benchmark_id=benchmark_id,
        status=status,
        domain=domain,
        scenario_id=scenario_id,
        result=result,
        created_from=created_from,
        created_to=created_to,
        limit=limit,
        offset=offset,
    )
    return {"total": len(runs), "limit": limit, "offset": offset, "items": [_benchmark_run_payload(run, compact=True) for run in runs]}


@router.get("/benchmark-runs/{benchmark_run_id}", dependencies=[Depends(require_api_key)])
def get_benchmark_run(benchmark_run_id: str, db: Session = Depends(get_db)) -> dict:
    run = BenchmarkRunRepository(db).get(benchmark_run_id)
    if not run:
        raise ValueError(f"Benchmark run not found: {benchmark_run_id}")
    return _benchmark_run_payload(run)


@router.get("/benchmark-runs/{benchmark_run_id}/artifact-manifest", dependencies=[Depends(require_api_key)])
def get_benchmark_run_artifact_manifest(benchmark_run_id: str, db: Session = Depends(get_db)) -> dict:
    run = BenchmarkRunRepository(db).get(benchmark_run_id)
    if not run:
        raise ValueError(f"Benchmark run not found: {benchmark_run_id}")
    return json.loads(run.artifact_manifest_json or "{}")


@router.post("/benchmark-runs/{benchmark_run_id}/cancel", dependencies=[Depends(require_api_key)])
def cancel_benchmark_run(benchmark_run_id: str, db: Session = Depends(get_db)) -> dict:
    run = BenchmarkRunRepository(db).get(benchmark_run_id)
    if not run:
        raise ValueError(f"Benchmark run not found: {benchmark_run_id}")
    if run.status in {"queued", "created"}:
        _set_benchmark_run_status(run, "cancelled", "Cancelled before generation started.")
        run.completed_at = datetime.now(timezone.utc)
    elif run.status in {"waiting_for_detector", "evaluation_failed"}:
        _set_benchmark_run_status(run, "cancelled", "Cancelled before detector evaluation completed.")
        run.completed_at = datetime.now(timezone.utc)
    elif run.status == "generating":
        _set_benchmark_run_status(run, "cancellation_requested", "Cancellation requested; generation may already be running.")
    else:
        raise HTTPException(status_code=409, detail={"error": {"code": "INVALID_BENCHMARK_STATE", "message": f"Cannot cancel benchmark run in status {run.status}", "details": {"status": run.status}}})
    db.commit()
    logger.info("benchmark_run_cancelled", extra={"benchmark_run_id": run.id, "status": run.status})
    return _benchmark_run_payload(run)


@router.post("/benchmark-runs/{benchmark_run_id}/retry-generation", dependencies=[Depends(require_api_key)])
def retry_benchmark_generation(benchmark_run_id: str, background_tasks: BackgroundTasks, request: Request, db: Session = Depends(get_db)) -> dict:
    run = BenchmarkRunRepository(db).get(benchmark_run_id)
    if not run:
        raise ValueError(f"Benchmark run not found: {benchmark_run_id}")
    if run.status != "generation_failed":
        raise HTTPException(status_code=409, detail={"error": {"code": "INVALID_BENCHMARK_STATE", "message": "Only generation_failed benchmark runs can retry generation.", "details": {"status": run.status}}})
    _set_benchmark_run_status(run, "queued", "Retry queued.")
    db.commit()
    background_tasks.add_task(_execute_benchmark_run, run.id, request.app.state.SessionLocal)
    return {"benchmark_run_id": run.id, "status": run.status}


@router.post("/benchmark-runs/{benchmark_run_id}/detector-output", dependencies=[Depends(require_api_key)])
def submit_benchmark_detector_output(benchmark_run_id: str, payload: BenchmarkRunDetectorSubmissionRequest, db: Session = Depends(get_db)) -> dict:
    return _submit_detector_output_for_benchmark_run(
        db,
        benchmark_run_id=benchmark_run_id,
        detector_name=payload.detector_name,
        detector_version=payload.detector_version,
        detector_output_format=payload.detector_output_format,
        detector_payload={"detector_name": payload.detector_name, "detector_version": payload.detector_version, "detections": payload.detections},
        label_mapping=payload.label_mapping,
        replace_existing=payload.replace_existing,
    )


@router.post("/benchmark-runs/{benchmark_run_id}/detector-output/upload", dependencies=[Depends(require_api_key)])
async def upload_benchmark_detector_output(
    benchmark_run_id: str,
    file: UploadFile = File(...),
    detector_name: str = Query(default="uploaded-detector"),
    detector_version: str | None = Query(default=None),
    replace_existing: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> dict:
    payload_text = await _read_detector_upload(file)
    detector_format = _detector_format_from_filename(file.filename or "")
    detector_payload = _parse_detector_payload(detector_format, payload_text)
    return _submit_detector_output_for_benchmark_run(
        db,
        benchmark_run_id=benchmark_run_id,
        detector_name=detector_name or detector_payload.get("detector_name", "uploaded-detector"),
        detector_version=detector_version or detector_payload.get("detector_version"),
        detector_output_format=detector_format,
        detector_payload=detector_payload,
        label_mapping={},
        replace_existing=replace_existing,
    )


@router.get("/scenario-library/scenarios")
def scenario_library_items(
    domain: str | None = None,
    business_process: str | None = None,
    failure_category: str | None = None,
    severity: str | None = None,
    execution_status: str | None = None,
    implementation_readiness: str | None = None,
    v1_ready: bool | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
) -> dict:
    items = expanded_scenario_items()
    quality_summary = load_scenario_quality_summary()
    v1_ready_ids = set()
    try:
        from dataforge.scenarios.catalog import load_scenario_quality_audit

        v1_ready_ids = {row["scenario_id"] for row in load_scenario_quality_audit().get("scenarios", []) if row.get("quality_status") == "v1_ready"}
    except Exception:
        v1_ready_ids = set()
    if domain:
        items = tuple(item for item in items if item.domain == domain)
    if business_process:
        items = tuple(item for item in items if item.business_process == business_process)
    if failure_category:
        items = tuple(item for item in items if item.failure_category == failure_category)
    if severity:
        items = tuple(item for item in items if item.severity == severity)
    if execution_status:
        items = tuple(item for item in items if item.execution_status == execution_status)
    if implementation_readiness:
        items = tuple(item for item in items if item.implementation_readiness == implementation_readiness)
    if v1_ready is not None:
        items = tuple(item for item in items if (item.scenario_id in v1_ready_ids) is v1_ready)
    summaries = [
        {
            "scenario_id": item.scenario_id,
            "scenario_name": item.scenario_name,
            "description": item.description,
            "domain": item.domain,
            "business_process": item.business_process,
            "severity": item.severity,
            "failure_category": item.failure_category,
            "failure_primitive": item.failure_primitive,
            "failure_display_name": primitive_display_name(item.failure_primitive),
            "validator_pattern": item.validator_pattern,
            "v1_ready": item.scenario_id in v1_ready_ids,
            "score": item.score.model_dump() if item.score else None,
            "execution_status": item.execution_status,
            "implementation_readiness": item.implementation_readiness,
            "implementation_dependencies": item.implementation_dependencies.model_dump(),
            "requirement_resolution": REQUIREMENT_RESOLVER.resolve(item).model_dump(),
            "semantic_requirements": {
                "required_columns": item.required_columns,
                "resolved_columns": [
                    COLUMN_SEMANTIC_RESOLVER.resolve_for_scenario_tables(item.domain, item.related_tables, column).model_dump()
                    for column in item.required_columns
                ],
            },
        }
        for item in items[:limit]
    ]
    return {"total": len(items), "returned": len(summaries), "quality_summary": quality_summary, "items": summaries}


@router.get("/scenarios/domains/{domain}")
def scenarios_by_domain(domain: str) -> dict:
    if domain not in DOMAIN_SPECS:
        raise ValueError(f"Unsupported domain: {domain}")
    scenarios = find_scenarios(domain=domain)
    return {"domain": domain, "total": len(scenarios), "items": [scenario_summary(scenario) for scenario in scenarios]}


@router.get("/scenarios/{scenario_id}")
def scenario_detail(scenario_id: str) -> dict:
    return get_scenario(scenario_id).model_dump()


@router.post("/scenarios/{scenario_id}/validate-config", dependencies=[Depends(require_api_key)])
def validate_scenario_config(scenario_id: str, payload: ScenarioConfigRequest) -> dict:
    config = ScenarioRunConfig(**{**payload.model_dump(), "scenario_id": scenario_id})
    return resolve_config(config).model_dump()


@router.post("/scenarios/{scenario_id}/run", response_model=GenerateResponse, dependencies=[Depends(require_api_key)])
def run_scenario(
    scenario_id: str,
    payload: ScenarioConfigRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, str | None]:
    config = ScenarioRunConfig(**{**payload.model_dump(), "scenario_id": scenario_id})
    generation_payload = GenerateRequest(**build_generation_payload(config))
    response = GenerationJobService(db).enqueue(generation_payload)
    background_tasks.add_task(run_generation_job, response["job_id"], request.app.state.SessionLocal)
    return response


@router.post("/scenarios/{scenario_id}/stream/start", response_model=StreamStartResponse, dependencies=[Depends(require_api_key)])
def start_scenario_stream(
    scenario_id: str,
    payload: ScenarioConfigRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    if scenario_id != "telecom_tower_congestion":
        raise ValueError("Only telecom_tower_congestion supports deep scenario streaming in Phase D2")
    scenario = get_scenario(scenario_id)
    config = ScenarioRunConfig(**{**payload.model_dump(), "scenario_id": scenario_id, "mode": "streaming", "output_format": "json"})
    validation = resolve_config(config)
    if validation.status != "PASS" or not validation.resolved_config:
        raise ValueError("; ".join(validation.errors))
    resolved = validation.resolved_config
    stream_payload = StreamStartRequest(
        domain="telecommunications",
        event_types=resolved.event_type_selection or ["call_detail_event", "data_session_event", "tower_outage_event"],
        events_per_second=resolved.event_rate or 10,
        duration_minutes=max(1, int((resolved.duration_seconds or 60) / 60)),
        format="json",
        seed=resolved.seed,
        failure_injections={},
        scenario_id=scenario.scenario_id,
        scenario_run_config=resolved.model_dump(),
        scenario_definition=scenario.model_dump(),
    )
    response = StreamSessionService(db).start(stream_payload)
    _attach_stream_integration_urls(response, request)
    background_tasks.add_task(run_stream_session, response["stream_id"], request.app.state.SessionLocal)
    return response


@router.get("/scenario-runs/{run_id}", dependencies=[Depends(require_api_key)])
def scenario_run_detail(run_id: str, db: Session = Depends(get_db)) -> dict:
    run = DatasetRunRepository(db).get(run_id)
    if not run:
        raise ValueError(f"Run not found: {run_id}")
    return {**_run_summary(run), "scenario_reports": _scenario_reports_for_run(run.id)}


def _scenario_reports_for_run(run_id: str) -> dict:
    root = get_settings().output_dir / run_id
    reports = {}
    for report_name in ("scenario_definition.json", "scenario_run_config.json", "scenario_execution_report.json", "expected_validations.json"):
        report_path = root / report_name
        if not report_path.exists():
            report_path = root / "reports" / report_name
        if report_path.exists():
            reports[report_name] = json.loads(report_path.read_text(encoding="utf-8"))
    return reports


def _ground_truth_payload_for_run(run) -> dict:
    reports = _scenario_reports_for_run(run.id)
    execution = reports.get("scenario_execution_report.json")
    if not execution or execution.get("ground_truth") is None:
        raise ValueError(f"Run does not contain scenario ground truth: {run.id}")
    return ground_truth_from_scenario_report(
        run_id=run.id,
        scenario_report=execution,
        generated_at=(run.completed_at or run.started_at).isoformat(),
        candidate_universe=_candidate_universe_for_run(run, execution),
    )


def _dataset_manifest_for_run(run) -> dict:
    reports = _scenario_reports_for_run(run.id)
    execution = reports.get("scenario_execution_report.json")
    if not execution:
        raise ValueError(f"Run does not contain scenario metadata: {run.id}")
    ground_truth = _ground_truth_payload_for_run(run)
    jsonl = ground_truth_to_jsonl(ground_truth)
    csv_payload = ground_truth_to_csv(ground_truth)
    table_counts = _table_counts_for_run(run)
    primary_keys = {table: schema.primary_key for table, schema in DOMAIN_SPECS.get(run.domain).schemas.items()} if run.domain in DOMAIN_SPECS else {}
    return dataset_manifest(
        run_id=run.id,
        scenario_report=execution,
        generated_files=[
            {
                "file_name": item.file_name,
                "file_format": item.file_format,
                "size_bytes": item.size_bytes,
                "content_type": item.content_type,
                "storage_backend": item.storage_backend,
            }
            for item in run.generated_files
        ],
        table_counts=table_counts,
        primary_keys=primary_keys,
        ground_truth_artifacts={
            "jsonl": {"path": f"/api/v1/scenario-library/runs/{run.id}/ground-truth?format=jsonl", "checksum_sha256": checksum_bytes(jsonl), "bytes": len(jsonl)},
            "csv": {"path": f"/api/v1/scenario-library/runs/{run.id}/ground-truth?format=csv", "checksum_sha256": checksum_bytes(csv_payload), "bytes": len(csv_payload)},
        },
    )


def _candidate_universe_for_run(run, scenario_report: dict) -> dict[str, set[str]]:
    target_tables = {((row.get("target") or {}).get("table")) for row in scenario_report.get("ground_truth", []) or []}
    target_tables.discard(None)
    if not target_tables:
        target_tables = {Path(item.file_name).stem for item in run.generated_files}
    primary_keys = {table: schema.primary_key for table, schema in DOMAIN_SPECS.get(run.domain).schemas.items()} if run.domain in DOMAIN_SPECS else {}
    universe: dict[str, set[str]] = {table: set() for table in target_tables}
    storage = get_storage_service()
    if not isinstance(storage, LocalStorageService):
        _seed_universe_from_ground_truth(universe, scenario_report)
        return universe
    for generated_file in run.generated_files:
        table = Path(generated_file.file_name).stem
        if table not in universe:
            continue
        pk = primary_keys.get(table) or _infer_primary_key(table)
        try:
            path = storage.resolve_path(generated_file)
            universe[table].update(_read_primary_keys(path, generated_file.file_format, pk))
        except Exception:
            continue
    _seed_universe_from_ground_truth(universe, scenario_report)
    return universe


def _seed_universe_from_ground_truth(universe: dict[str, set[str]], scenario_report: dict) -> None:
    for row in scenario_report.get("ground_truth", []) or []:
        table = (row.get("target") or {}).get("table")
        if not table:
            continue
        universe.setdefault(table, set()).update(str(value) for value in row.get("affected_entities", []) or [])


def _read_primary_keys(path: Path, file_format: str, primary_key: str) -> set[str]:
    if file_format == "csv":
        with path.open(newline="", encoding="utf-8") as handle:
            return {str(row[primary_key]) for row in csv.DictReader(handle) if row.get(primary_key)}
    if file_format == "json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows = payload if isinstance(payload, list) else payload.get("rows", []) if isinstance(payload, dict) else []
        return {str(row[primary_key]) for row in rows if isinstance(row, dict) and row.get(primary_key)}
    return set()


def _table_counts_for_run(run) -> dict[str, int]:
    counts: dict[str, int] = {}
    storage = get_storage_service()
    for generated_file in run.generated_files:
        table = Path(generated_file.file_name).stem
        if not isinstance(storage, LocalStorageService):
            counts[table] = run.record_count
            continue
        try:
            path = storage.resolve_path(generated_file)
            if generated_file.file_format == "csv":
                with path.open(newline="", encoding="utf-8") as handle:
                    counts[table] = max(0, sum(1 for _ in handle) - 1)
            elif generated_file.file_format == "json":
                payload = json.loads(path.read_text(encoding="utf-8"))
                counts[table] = len(payload if isinstance(payload, list) else payload.get("rows", []))
            else:
                counts[table] = run.record_count
        except Exception:
            counts[table] = run.record_count
    return counts


def _create_evaluation_result(
    db: Session,
    *,
    run_id: str,
    detector_name: str,
    detector_version: str | None,
    detector_output_format: str,
    detections: list[dict],
    label_mapping: dict[str, str],
    benchmark=None,
) -> dict:
    run = DatasetRunRepository(db).get(run_id)
    if not run:
        raise ValueError(f"Run not found: {run_id}")
    started_at = datetime.now(timezone.utc)
    detector_payload = {"detector_name": detector_name, "detector_version": detector_version, "detections": detections}
    ground_truth = _ground_truth_payload_for_run(run)
    result = evaluate_detector_output(ground_truth, detector_payload, label_mapping=label_mapping)
    if benchmark:
        thresholds = json.loads(benchmark.thresholds_json or "{}")
        result["acceptance"] = acceptance_status(result["metrics"], thresholds)
        status_value = result["acceptance"]["status"]
    else:
        result["acceptance"] = {"status": "NOT_APPLICABLE", "failures": []}
        status_value = "completed"
    artifacts = _persist_evaluation_artifacts(run.id, detector_payload, result)
    detector_bytes = json.dumps(detector_payload, sort_keys=True, default=str).encode("utf-8")
    evaluation = EvaluationRunRepository(db).create(
        scenario_run_id=run.id,
        benchmark_id=benchmark.id if benchmark else None,
        benchmark_version=benchmark.version if benchmark else None,
        detector_name=detector_name,
        detector_version=detector_version,
        detector_output_format=detector_output_format,
        detector_output_checksum=checksum_bytes(detector_bytes),
        detector_output_artifact=artifacts["detector_output"],
        result_artifact=artifacts["result"],
        metrics_json=json.dumps(result, default=str),
        status=status_value,
        started_at=started_at,
        completed_at=datetime.now(timezone.utc),
    )
    db.commit()
    return _evaluation_payload(evaluation)


def _parse_detector_payload(detector_output_format: str, payload: str) -> dict:
    try:
        if detector_output_format == "jsonl":
            return detector_payload_from_jsonl(payload)
        if detector_output_format == "csv":
            return detector_payload_from_csv(payload)
        parsed = json.loads(payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail={"error": {"code": "INVALID_DETECTOR_OUTPUT", "message": "Detector output could not be parsed.", "details": {"format": detector_output_format}}}) from exc
    if isinstance(parsed, list):
        return {"detector_name": "json-detector", "detections": parsed}
    if isinstance(parsed, dict):
        return parsed
    raise HTTPException(status_code=400, detail={"error": {"code": "INVALID_DETECTOR_OUTPUT", "message": "Detector JSON payload must be an object or an array.", "details": {}}})


BENCHMARK_RUN_TRANSITIONS = {
    "created": {"queued", "cancelled"},
    "queued": {"generating", "cancelled"},
    "generating": {"waiting_for_detector", "generation_failed", "cancellation_requested"},
    "cancellation_requested": {"cancelled", "generation_failed", "waiting_for_detector"},
    "generation_failed": {"queued"},
    "waiting_for_detector": {"detector_received", "cancelled"},
    "detector_received": {"evaluating"},
    "evaluating": {"completed", "evaluation_failed"},
    "evaluation_failed": {"detector_received", "cancelled"},
    "completed": set(),
    "cancelled": set(),
}


def _create_benchmark_run(db: Session, benchmark, payload: BenchmarkRunRequest, *, idempotency_key: str | None) -> tuple[object, bool]:
    request_body = payload.model_dump()
    fingerprint = checksum_bytes(json.dumps({"benchmark_id": benchmark.id, **request_body}, sort_keys=True, default=str).encode("utf-8"))
    repo = BenchmarkRunRepository(db)
    if idempotency_key:
        existing = repo.get_by_idempotency_key(idempotency_key)
        if existing:
            if existing.request_fingerprint != fingerprint:
                raise HTTPException(
                    status_code=409,
                    detail={"error": {"code": "IDEMPOTENCY_CONFLICT", "message": "Idempotency-Key was reused with a different benchmark run request.", "details": {"benchmark_run_id": existing.id}}},
                )
            return existing, False
    if repo.count_active() >= get_settings().benchmark_concurrent_runs:
        raise HTTPException(
            status_code=429,
            detail={
                "error": {
                    "code": "QUOTA_EXCEEDED",
                    "message": "Benchmark concurrency limit reached.",
                    "details": {"limit": get_settings().benchmark_concurrent_runs},
                }
            },
        )

    seed = _effective_benchmark_seed(benchmark, payload)
    snapshot = _benchmark_run_snapshot(benchmark, seed=seed, detector_mode=payload.detector_mode)
    now = datetime.now(timezone.utc)
    run = repo.create(
        benchmark_id=benchmark.id,
        benchmark_version=benchmark.version,
        domain=benchmark.domain,
        scenario_id=benchmark.scenario_id,
        status="queued",
        status_reason="Benchmark run queued for scenario generation.",
        detector_mode=payload.detector_mode,
        detector_status="not_submitted",
        artifact_manifest_json="{}",
        snapshot_json=json.dumps(snapshot, default=str),
        idempotency_key=idempotency_key,
        request_fingerprint=fingerprint,
        retain_until=now + timedelta(days=get_settings().benchmark_artifact_retention_days),
    )
    return run, True


def _effective_benchmark_seed(benchmark, payload: BenchmarkRunRequest) -> int:
    if payload.seed_mode == "random":
        return int(datetime.now(timezone.utc).timestamp() * 1_000_000) % 2_147_483_647
    return payload.seed if payload.seed is not None else benchmark.seed


def _benchmark_run_snapshot(benchmark, *, seed: int, detector_mode: str) -> dict:
    scenario = get_expanded_scenario(benchmark.scenario_id)
    failure_plan = json.loads(benchmark.failure_plan_json)
    failure_plan["seed"] = seed
    return {
        "snapshot_version": "1.0",
        "benchmark_id": benchmark.id,
        "benchmark_name": benchmark.name,
        "benchmark_version": benchmark.version,
        "scenario_id": benchmark.scenario_id,
        "scenario_version": scenario.version,
        "dataset_configuration": {
            "domain": benchmark.domain,
            "records": benchmark.records,
            "output_format": benchmark.output_format,
            "load_type": "bulk",
        },
        "failure_plan": failure_plan,
        "seed": seed,
        "detector_mode": detector_mode,
        "ground_truth_version": "1.0",
        "evaluation_unit": benchmark.evaluation_unit,
        "evaluation_key_fields": _evaluation_key_fields_for_benchmark(benchmark),
        "acceptance_thresholds": json.loads(benchmark.thresholds_json or "{}"),
        "generator_version": "0.6.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def _evaluation_key_fields_for_benchmark(benchmark) -> dict[str, str]:
    if benchmark.domain not in DOMAIN_SPECS:
        return {}
    return {table: schema.primary_key for table, schema in DOMAIN_SPECS[benchmark.domain].schemas.items()}


def _set_benchmark_run_status(run, next_status: str, reason: str | None = None) -> None:
    allowed = BENCHMARK_RUN_TRANSITIONS.get(run.status, set())
    if next_status not in allowed and run.status != next_status:
        raise HTTPException(
            status_code=409,
            detail={"error": {"code": "INVALID_BENCHMARK_STATE", "message": f"Invalid benchmark transition {run.status} -> {next_status}", "details": {"from": run.status, "to": next_status}}},
        )
    run.status = next_status
    run.status_reason = reason


def _execute_benchmark_run(benchmark_run_id: str, session_factory) -> None:
    db = session_factory()
    try:
        benchmark_run = BenchmarkRunRepository(db).get(benchmark_run_id)
        if not benchmark_run:
            logger.error("benchmark_run_not_found", extra={"benchmark_run_id": benchmark_run_id})
            return
        if benchmark_run.status == "cancelled":
            return
        benchmark = BenchmarkDefinitionRepository(db).get(benchmark_run.benchmark_id)
        if not benchmark:
            _set_benchmark_run_status(benchmark_run, "generation_failed", "Benchmark definition no longer exists.")
            db.commit()
            return
        _set_benchmark_run_status(benchmark_run, "generating", "Generating benchmark dataset.")
        benchmark_run.started_at = datetime.now(timezone.utc)
        db.commit()

        generation_payload = _generation_payload_for_benchmark(benchmark, json.loads(benchmark_run.snapshot_json))
        job_response = GenerationJobService(db).enqueue(generation_payload)
        benchmark_run = BenchmarkRunRepository(db).get(benchmark_run_id)
        if benchmark_run:
            benchmark_run.generation_job_id = job_response["job_id"]
            db.commit()

        logger.info("benchmark_generation_started", extra={"benchmark_run_id": benchmark_run_id, "job_id": job_response["job_id"]})
        run_generation_job(job_response["job_id"], session_factory)

        benchmark_run = BenchmarkRunRepository(db).get(benchmark_run_id)
        job = GenerationJobRepository(db).get(job_response["job_id"])
        if not benchmark_run or not job:
            return
        if benchmark_run.status == "cancellation_requested":
            _set_benchmark_run_status(benchmark_run, "cancelled", "Cancelled after generation returned.")
            benchmark_run.completed_at = datetime.now(timezone.utc)
            db.commit()
            return
        if job.status != "completed" or not job.run_id:
            _set_benchmark_run_status(benchmark_run, "generation_failed", job.error_message or "Scenario generation failed.")
            benchmark_run.completed_at = datetime.now(timezone.utc)
            db.commit()
            logger.info("benchmark_generation_failed", extra={"benchmark_run_id": benchmark_run_id, "job_id": job_response["job_id"]})
            return

        scenario_run = DatasetRunRepository(db).get(job.run_id)
        if not scenario_run:
            _set_benchmark_run_status(benchmark_run, "generation_failed", "Scenario run was not found after generation.")
            benchmark_run.completed_at = datetime.now(timezone.utc)
            db.commit()
            return
        manifest = _benchmark_artifact_manifest(benchmark_run, scenario_run)
        _persist_benchmark_artifact_manifest(scenario_run.id, manifest)
        benchmark_run.scenario_run_id = scenario_run.id
        benchmark_run.artifact_manifest_json = json.dumps(manifest, default=str)
        _set_benchmark_run_status(benchmark_run, "waiting_for_detector", "Dataset and ground truth are ready. Awaiting detector output.")
        db.commit()
        logger.info("benchmark_generation_completed", extra={"benchmark_run_id": benchmark_run_id, "scenario_run_id": scenario_run.id})
    except Exception as error:
        db.rollback()
        benchmark_run = BenchmarkRunRepository(db).get(benchmark_run_id)
        if benchmark_run and benchmark_run.status in {"queued", "generating", "cancellation_requested"}:
            try:
                _set_benchmark_run_status(benchmark_run, "generation_failed", str(error))
            except HTTPException:
                benchmark_run.status = "generation_failed"
                benchmark_run.status_reason = str(error)
            benchmark_run.completed_at = datetime.now(timezone.utc)
            db.commit()
        logger.exception("benchmark_run_generation_failed", extra={"benchmark_run_id": benchmark_run_id})
    finally:
        db.close()


def _generation_payload_for_benchmark(benchmark, snapshot: dict) -> GenerateRequest:
    scenario = get_expanded_scenario(benchmark.scenario_id)
    failure_plan = snapshot["failure_plan"]
    records = int(snapshot["dataset_configuration"]["records"])
    selected_tables = [row["table"] for row in build_scenario_configuration(benchmark.scenario_id, records=records)["required_tables"]]
    preview = preview_failure_plan(benchmark.scenario_id, FailurePlan.model_validate(failure_plan), records=records)
    if not preview["valid"]:
        raise ValueError("; ".join(preview["errors"]))
    return GenerateRequest(
        domain=scenario.domain,
        load_type="bulk",
        format=benchmark.output_format,
        records=records,
        selected_tables=selected_tables,
        issues={},
        user_email="benchmark@dataforge.local",
        scenario_id=scenario.scenario_id,
        scenario_run_config={
            "scenario_id": scenario.scenario_id,
            "domain": scenario.domain,
            "mode": "batch",
            "records": records,
            "output_format": benchmark.output_format,
            "seed": failure_plan.get("seed", benchmark.seed),
            "severity": "medium",
            "failure_plan": failure_plan,
            "benchmark_run": {"benchmark_id": benchmark.id, "benchmark_version": benchmark.version},
        },
        scenario_definition=scenario.model_dump(),
        expected_validations={"scenario_id": scenario.scenario_id, "validator_pattern": scenario.validator_pattern, "expected_quality_status": "FAIL"},
        scenario_execution_report={
            "scenario_id": scenario.scenario_id,
            "scenario_version": scenario.version,
            "configuration": {"records": records, "output_format": benchmark.output_format, "seed": failure_plan.get("seed", benchmark.seed), "severity": "medium"},
            "generation_plan_preview": preview,
            "ground_truth_contract": "ground_truth_contract.yaml",
            "benchmark_snapshot": snapshot,
            "reconciliation_result": "PENDING",
            "scenario_outcome": "PENDING",
            "warnings": preview.get("warnings", []),
        },
        failure_plan=failure_plan,
    )


def _benchmark_artifact_manifest(benchmark_run, scenario_run) -> dict:
    dataset_manifest_payload = _dataset_manifest_for_run(scenario_run)
    ground_truth_json = ground_truth_to_jsonl(_ground_truth_payload_for_run(scenario_run))
    return {
        "manifest_version": "1.0",
        "benchmark_run_id": benchmark_run.id,
        "benchmark_id": benchmark_run.benchmark_id,
        "benchmark_version": benchmark_run.benchmark_version,
        "scenario_run_id": scenario_run.id,
        "artifacts": {
            "dataset": [
                {
                    "file_id": item.id,
                    "file_name": item.file_name,
                    "download_url": f"/api/v1/runs/{scenario_run.id}/files/{item.id}/download",
                    "size_bytes": item.size_bytes,
                    "content_type": item.content_type,
                }
                for item in scenario_run.generated_files
            ],
            "dataset_zip": f"/api/v1/runs/{scenario_run.id}/download",
            "manifest": f"/api/v1/scenario-library/runs/{scenario_run.id}/manifest",
            "ground_truth_json": f"/api/v1/scenario-library/runs/{scenario_run.id}/ground-truth?format=json",
            "ground_truth_jsonl": f"/api/v1/scenario-library/runs/{scenario_run.id}/ground-truth?format=jsonl",
            "ground_truth_csv": f"/api/v1/scenario-library/runs/{scenario_run.id}/ground-truth?format=csv",
            "scenario_report": f"/api/v1/scenario-library/runs/{scenario_run.id}",
        },
        "checksums": {
            "ground_truth_jsonl_sha256": checksum_bytes(ground_truth_json),
            "dataset_manifest_sha256": checksum_bytes(json.dumps(dataset_manifest_payload, sort_keys=True, default=str).encode("utf-8")),
        },
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def _persist_benchmark_artifact_manifest(scenario_run_id: str, manifest: dict) -> None:
    path = get_settings().output_dir / scenario_run_id / "reports" / "benchmark_artifact_manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")


def _submit_detector_output_for_benchmark_run(
    db: Session,
    *,
    benchmark_run_id: str,
    detector_name: str,
    detector_version: str | None,
    detector_output_format: str,
    detector_payload: dict,
    label_mapping: dict[str, str],
    replace_existing: bool,
) -> dict:
    repo = BenchmarkRunRepository(db)
    benchmark_run = repo.get(benchmark_run_id)
    if not benchmark_run:
        raise ValueError(f"Benchmark run not found: {benchmark_run_id}")
    if benchmark_run.status in {"created", "queued", "generating", "generation_failed"}:
        raise HTTPException(status_code=409, detail={"error": {"code": "BENCHMARK_NOT_READY_FOR_DETECTOR", "message": "Benchmark dataset must be generated before detector output can be submitted.", "details": {"status": benchmark_run.status}}})
    if benchmark_run.status in {"completed", "cancelled"} and not replace_existing:
        raise HTTPException(status_code=409, detail={"error": {"code": "INVALID_BENCHMARK_STATE", "message": "Detector output was already evaluated. Use replace_existing=true to submit a corrected result.", "details": {"status": benchmark_run.status}}})
    if benchmark_run.status == "detector_received" and not replace_existing:
        raise HTTPException(status_code=409, detail={"error": {"code": "INVALID_BENCHMARK_STATE", "message": "Detector output already submitted.", "details": {"status": benchmark_run.status}}})
    if not benchmark_run.scenario_run_id:
        raise HTTPException(status_code=409, detail={"error": {"code": "ARTIFACT_NOT_AVAILABLE", "message": "Benchmark run has no generated scenario run.", "details": {}}})
    _validate_detector_payload_or_400(detector_payload, label_mapping)

    if benchmark_run.status in {"waiting_for_detector", "evaluation_failed"}:
        _set_benchmark_run_status(benchmark_run, "detector_received", "Detector output accepted.")
    else:
        benchmark_run.status = "detector_received"
        benchmark_run.status_reason = "Detector output accepted for replacement evaluation."
    benchmark_run.detector_status = "received"
    benchmark_run.detector_name = detector_name
    benchmark_run.detector_version = detector_version
    benchmark_run.detector_output_artifact = _persist_benchmark_detector_payload(benchmark_run, detector_payload, detector_output_format)
    db.commit()

    try:
        _set_benchmark_run_status(benchmark_run, "evaluating", "Evaluating detector output against ground truth.")
        benchmark_run.detector_status = "evaluating"
        db.commit()
        benchmark = BenchmarkDefinitionRepository(db).get(benchmark_run.benchmark_id)
        if not benchmark:
            raise ValueError(f"Benchmark not found: {benchmark_run.benchmark_id}")
        evaluation = _create_evaluation_result(
            db,
            run_id=benchmark_run.scenario_run_id,
            detector_name=detector_name,
            detector_version=detector_version,
            detector_output_format=detector_output_format,
            detections=detector_payload.get("detections", []),
            label_mapping=label_mapping,
            benchmark=benchmark,
        )
        benchmark_run = repo.get(benchmark_run_id)
        if benchmark_run:
            benchmark_run.evaluation_run_id = evaluation["id"]
            benchmark_run.metrics_json = json.dumps(evaluation["metrics"], default=str)
            benchmark_run.acceptance_json = json.dumps(evaluation["acceptance"], default=str)
            benchmark_run.result = evaluation["acceptance"]["status"]
            benchmark_run.detector_status = "evaluated"
            _set_benchmark_run_status(benchmark_run, "completed", f"Benchmark {benchmark_run.result}.")
            benchmark_run.completed_at = datetime.now(timezone.utc)
            db.commit()
            logger.info("benchmark_evaluation_completed", extra={"benchmark_run_id": benchmark_run_id, "result": benchmark_run.result})
            return _benchmark_run_payload(benchmark_run)
    except Exception as error:
        db.rollback()
        benchmark_run = repo.get(benchmark_run_id)
        if benchmark_run:
            try:
                _set_benchmark_run_status(benchmark_run, "evaluation_failed", str(error))
            except HTTPException:
                benchmark_run.status = "evaluation_failed"
                benchmark_run.status_reason = str(error)
            benchmark_run.detector_status = "failed"
            db.commit()
        raise
    raise ValueError("Benchmark evaluation did not complete")


def _validate_detector_payload_or_400(detector_payload: dict, label_mapping: dict[str, str]) -> None:
    detections = detector_payload.get("detections")
    if detections is None:
        detector_payload["detections"] = []
        return
    if not isinstance(detections, list):
        raise HTTPException(status_code=400, detail={"error": {"code": "INVALID_DETECTOR_OUTPUT", "message": "Detector output detections must be a list.", "details": {}}})
    _, errors = normalize_detector_output(detector_payload, label_mapping=label_mapping)
    if errors:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "INVALID_DETECTOR_OUTPUT", "message": "Detector output contains invalid detection rows.", "details": {"errors": errors[:10]}}},
        )


def _persist_benchmark_detector_payload(benchmark_run, detector_payload: dict, detector_output_format: str) -> str:
    root = get_settings().output_dir / "benchmark_runs" / benchmark_run.id
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"detector_output.{detector_output_format}"
    path.write_text(json.dumps(detector_payload, indent=2, default=str), encoding="utf-8")
    return path.relative_to(get_settings().output_dir).as_posix()


async def _read_detector_upload(file: UploadFile) -> str:
    filename = file.filename or ""
    if Path(filename).name != filename or not filename:
        raise HTTPException(status_code=400, detail={"error": {"code": "INVALID_DETECTOR_OUTPUT", "message": "Detector filename is invalid.", "details": {"filename": filename}}})
    _detector_format_from_filename(filename)
    payload = await file.read(get_settings().benchmark_detector_upload_max_bytes + 1)
    if len(payload) > get_settings().benchmark_detector_upload_max_bytes:
        raise HTTPException(status_code=413, detail={"error": {"code": "INVALID_DETECTOR_OUTPUT", "message": "Detector upload exceeds configured maximum size.", "details": {"max_bytes": get_settings().benchmark_detector_upload_max_bytes}}})
    try:
        return payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail={"error": {"code": "INVALID_DETECTOR_OUTPUT", "message": "Detector output must be UTF-8 text.", "details": {}}}) from exc


def _detector_format_from_filename(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".json":
        return "json"
    if suffix == ".jsonl":
        return "jsonl"
    if suffix == ".csv":
        return "csv"
    raise HTTPException(status_code=400, detail={"error": {"code": "INVALID_DETECTOR_OUTPUT", "message": "Unsupported detector output file type.", "details": {"supported": [".json", ".jsonl", ".csv"]}}})


def _benchmark_run_payload(run, *, compact: bool = False) -> dict:
    snapshot = json.loads(run.snapshot_json or "{}")
    artifact_manifest = json.loads(run.artifact_manifest_json or "{}")
    payload = {
        "id": run.id,
        "benchmark_id": run.benchmark_id,
        "benchmark_version": run.benchmark_version,
        "domain": run.domain,
        "scenario_id": run.scenario_id,
        "scenario_run_id": run.scenario_run_id,
        "generation_job_id": run.generation_job_id,
        "evaluation_run_id": run.evaluation_run_id,
        "status": run.status,
        "status_reason": run.status_reason,
        "detector_mode": run.detector_mode,
        "detector_status": run.detector_status,
        "detector_name": run.detector_name,
        "detector_version": run.detector_version,
        "dataset_status": "ready" if run.scenario_run_id else "pending",
        "ground_truth_status": "ready" if run.scenario_run_id else "pending",
        "evaluation_status": "completed" if run.evaluation_run_id else ("failed" if run.status == "evaluation_failed" else "pending"),
        "result": run.result,
        "acceptance": json.loads(run.acceptance_json) if run.acceptance_json else None,
        "metrics": json.loads(run.metrics_json) if run.metrics_json else None,
        "artifact_manifest": None if compact else artifact_manifest,
        "snapshot": None if compact else snapshot,
        "retain_until": run.retain_until.isoformat() if run.retain_until else None,
        "created_at": run.created_at.isoformat(),
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "updated_at": run.updated_at.isoformat(),
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "errors": [run.status_reason] if run.status in {"generation_failed", "evaluation_failed"} and run.status_reason else [],
        "warnings": _benchmark_run_warnings(run),
    }
    return payload


def _benchmark_run_warnings(run) -> list[str]:
    warnings = []
    if run.detector_mode not in {"manual_upload", "api_submission"}:
        warnings.append("Detector mode is reserved for future execution integrations.")
    return warnings


def _enforce_benchmark_quota(request: Request, idempotency_key: str | None) -> None:
    settings = get_settings()
    client_host = request.client.host if request.client else "unknown"
    token = request.headers.get("X-API-Key") or idempotency_key or "anonymous"
    rate_limiter.check(
        key=f"benchmark-run:{client_host}:{token}",
        limit=settings.benchmark_runs_per_period,
        window_seconds=settings.benchmark_run_period_seconds,
    )


def _persist_evaluation_artifacts(run_id: str, detector_payload: dict, result: dict) -> dict[str, str]:
    root = get_settings().output_dir / run_id / "reports" / "benchmarking"
    root.mkdir(parents=True, exist_ok=True)
    detector_path = root / f"detector_output_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}.json"
    result_path = root / f"evaluation_result_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}.json"
    detector_path.write_text(json.dumps(detector_payload, indent=2, default=str), encoding="utf-8")
    result_path.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    output_dir = get_settings().output_dir
    return {"detector_output": detector_path.relative_to(output_dir).as_posix(), "result": result_path.relative_to(output_dir).as_posix()}


def _evaluation_payload(evaluation) -> dict:
    result = json.loads(evaluation.metrics_json)
    return {
        "id": evaluation.id,
        "scenario_run_id": evaluation.scenario_run_id,
        "benchmark_id": evaluation.benchmark_id,
        "benchmark_version": evaluation.benchmark_version,
        "detector_name": evaluation.detector_name,
        "detector_version": evaluation.detector_version,
        "detector_output_format": evaluation.detector_output_format,
        "detector_output_checksum": evaluation.detector_output_checksum,
        "detector_output_artifact": evaluation.detector_output_artifact,
        "result_artifact": evaluation.result_artifact,
        "status": evaluation.status,
        "metrics": result.get("metrics", {}),
        "per_failure_metrics": result.get("per_failure_metrics", []),
        "acceptance": result.get("acceptance", {"status": "NOT_APPLICABLE", "failures": []}),
        "false_positive_examples": result.get("false_positive_examples", []),
        "false_negative_examples": result.get("false_negative_examples", []),
        "unknown_detections": result.get("unknown_detections", []),
        "started_at": evaluation.started_at.isoformat(),
        "completed_at": evaluation.completed_at.isoformat() if evaluation.completed_at else None,
        "created_at": evaluation.created_at.isoformat(),
    }


def _benchmark_payload(benchmark) -> dict:
    return {
        "id": benchmark.id,
        "name": benchmark.name,
        "slug": benchmark.slug,
        "version": benchmark.version,
        "description": benchmark.description,
        "domain": benchmark.domain,
        "scenario_id": benchmark.scenario_id,
        "scenario_template_id": benchmark.scenario_template_id,
        "records": benchmark.records,
        "output_format": benchmark.output_format,
        "seed": benchmark.seed,
        "failure_plan": json.loads(benchmark.failure_plan_json),
        "evaluation_unit": benchmark.evaluation_unit,
        "thresholds": json.loads(benchmark.thresholds_json or "{}"),
        "snapshot": json.loads(benchmark.snapshot_json or "{}"),
        "created_at": benchmark.created_at.isoformat(),
        "updated_at": benchmark.updated_at.isoformat(),
    }


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "benchmark"


def _infer_primary_key(table: str) -> str:
    if table.endswith("ies"):
        return f"{table[:-3]}y_id"
    if table.endswith("s"):
        return f"{table[:-1]}_id"
    return f"{table}_id"


@router.post("/validate", dependencies=[Depends(require_api_key)])
def validate_dataset(payload: ValidateRequest, db: Session = Depends(get_db)) -> dict:
    return ValidationService(db).validate_run(payload.run_id)


@router.post("/streams/start", response_model=StreamStartResponse, dependencies=[Depends(require_api_key)])
def start_stream(
    payload: StreamStartRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    response = StreamSessionService(db).start(payload)
    _attach_stream_integration_urls(response, request)
    background_tasks.add_task(run_stream_session, response["stream_id"], request.app.state.SessionLocal)
    return response


@router.get("/streams/{stream_id}", response_model=StreamStatusResponse, dependencies=[Depends(require_api_key)])
def get_stream(stream_id: str, db: Session = Depends(get_db)) -> dict:
    return StreamSessionService(db).status(stream_id)


@router.get("/streams/{stream_id}/events", response_model=StreamEventsResponse)
def get_stream_events(
    stream_id: str,
    request: Request,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    after_sequence: int | None = Query(default=None, ge=0),
    stream_token: str | None = Query(default=None),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    x_stream_token: str | None = Header(default=None, alias="X-Stream-Token"),
    authorization: str | None = Header(default=None, alias="Authorization"),
    db: Session = Depends(get_db),
) -> dict:
    _require_stream_access(request, db, stream_id, query_token=stream_token, x_api_key=x_api_key, x_stream_token=x_stream_token, authorization=authorization)
    return StreamSessionService(db).events(stream_id, limit=limit, offset=offset, after_sequence=after_sequence)


@router.get("/streams/{stream_id}/events/latest")
def get_latest_stream_event(
    stream_id: str,
    request: Request,
    stream_token: str | None = Query(default=None),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    x_stream_token: str | None = Header(default=None, alias="X-Stream-Token"),
    authorization: str | None = Header(default=None, alias="Authorization"),
    db: Session = Depends(get_db),
) -> dict:
    _require_stream_access(request, db, stream_id, query_token=stream_token, x_api_key=x_api_key, x_stream_token=x_stream_token, authorization=authorization)
    return StreamSessionService(db).latest_event(stream_id)


@router.get("/streams/{stream_id}/events/{event_type}", response_model=StreamEventsResponse)
def get_stream_events_by_type(
    stream_id: str,
    event_type: str,
    request: Request,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    after_sequence: int | None = Query(default=None, ge=0),
    stream_token: str | None = Query(default=None),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    x_stream_token: str | None = Header(default=None, alias="X-Stream-Token"),
    authorization: str | None = Header(default=None, alias="Authorization"),
    db: Session = Depends(get_db),
) -> dict:
    _require_stream_access(request, db, stream_id, query_token=stream_token, x_api_key=x_api_key, x_stream_token=x_stream_token, authorization=authorization)
    return StreamSessionService(db).events(stream_id, limit=limit, offset=offset, after_sequence=after_sequence, event_type=event_type)


@router.get("/streams/{stream_id}/sse")
def stream_events_sse(
    stream_id: str,
    request: Request,
    stream_token: str | None = Query(default=None),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    x_stream_token: str | None = Header(default=None, alias="X-Stream-Token"),
    authorization: str | None = Header(default=None, alias="Authorization"),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    _require_stream_access(request, db, stream_id, query_token=stream_token, x_api_key=x_api_key, x_stream_token=x_stream_token, authorization=authorization)
    events = StreamSessionService(db).events(stream_id, limit=1000, offset=0)["events"]

    return _sse_response(events)


@router.get("/streams/{stream_id}/sse/{event_type}")
def stream_events_sse_by_type(
    stream_id: str,
    event_type: str,
    request: Request,
    stream_token: str | None = Query(default=None),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    x_stream_token: str | None = Header(default=None, alias="X-Stream-Token"),
    authorization: str | None = Header(default=None, alias="Authorization"),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    _require_stream_access(request, db, stream_id, query_token=stream_token, x_api_key=x_api_key, x_stream_token=x_stream_token, authorization=authorization)
    events = StreamSessionService(db).events(stream_id, limit=1000, offset=0, event_type=event_type)["events"]

    return _sse_response(events)


def _sse_response(events: list[dict]) -> StreamingResponse:

    def event_iter():
        for event in events:
            yield f"event: data\ndata: {json.dumps(event)}\n\n"
        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(event_iter(), media_type="text/event-stream")


@router.post("/streams/{stream_id}/stop", response_model=StreamStatusResponse, dependencies=[Depends(require_api_key)])
def stop_stream(stream_id: str, db: Session = Depends(get_db)) -> dict:
    return StreamSessionService(db).stop(stream_id)


@router.post("/streams/{stream_id}/replay", response_model=StreamEventsResponse, dependencies=[Depends(require_api_key)])
def replay_stream(stream_id: str, db: Session = Depends(get_db)) -> dict:
    return StreamSessionService(db).replay(stream_id)


@router.get("/streams/{stream_id}/validation", dependencies=[Depends(require_api_key)])
def validate_stream(stream_id: str, db: Session = Depends(get_db)) -> dict:
    repo = StreamSessionService(db).sessions
    session = repo.get(stream_id)
    if not session:
        raise ValueError(f"Stream session not found: {stream_id}")
    events = repo.list_events(stream_id, limit=1000, offset=0)
    return stream_validation_report(session, events)


def _attach_stream_integration_urls(response: dict, request: Request) -> None:
    stream_id = response["stream_id"]
    response["pull_url"] = str(request.url_for("get_stream_events", stream_id=stream_id))
    response["sse_url"] = str(request.url_for("stream_events_sse", stream_id=stream_id))
    response["latest_url"] = str(request.url_for("get_latest_stream_event", stream_id=stream_id))
    response["event_type_urls"] = {
        event_type: str(request.url_for("get_stream_events_by_type", stream_id=stream_id, event_type=event_type))
        for event_type in STREAM_EVENT_TYPES.get(response["domain"], ())
    }


def _require_stream_access(
    request: Request,
    db: Session,
    stream_id: str,
    *,
    query_token: str | None,
    x_api_key: str | None,
    x_stream_token: str | None,
    authorization: str | None,
) -> None:
    settings = get_settings()
    if query_token and (settings.app_env.lower() == "production" or not settings.stream_query_token_enabled):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "Query-string stream tokens are disabled; use Authorization: Bearer or X-Stream-Token", "code": "UNAUTHORIZED"},
        )
    token = _stream_token_from_request(query_token, x_stream_token, authorization)
    enforce_rate_limit(request, token=token or x_api_key)
    if token:
        try:
            StreamSessionService(db).authorize_token(stream_id, token)
            return
        except PermissionError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"error": str(exc), "code": "UNAUTHORIZED"}) from exc

    expected_api_key = settings.api_key
    if not expected_api_key:
        return
    if x_api_key == expected_api_key:
        return
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"error": "Invalid or missing API key or stream token", "code": "UNAUTHORIZED"},
    )


def _stream_token_from_request(query_token: str | None, x_stream_token: str | None, authorization: str | None) -> str | None:
    if query_token:
        return query_token
    if x_stream_token:
        return x_stream_token
    if authorization and authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip()
    return None


@router.get("/runs", response_model=PaginatedRuns)
def list_runs(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: None = Depends(require_api_key),
) -> dict:
    settings = get_settings()
    cleanup_expired_run_history(db, settings.generated_file_retention_days, dry_run=False)
    db.commit()
    repo = DatasetRunRepository(db)
    runs = repo.list(limit=limit, offset=offset)
    return {
        "total": repo.count(),
        "limit": limit,
        "offset": offset,
        "items": [_run_summary(run) for run in runs],
    }


@router.get("/runs/{run_id}", response_model=RunDetail)
def get_run(run_id: str, db: Session = Depends(get_db), _: None = Depends(require_api_key)) -> dict:
    run = DatasetRunRepository(db).get(run_id)
    if not run:
        raise ValueError(f"Run not found: {run_id}")
    return {
        **_run_summary(run),
        "generated_files": [
            {
                "id": item.id,
                "file_name": item.file_name,
                "file_path": item.file_path,
                "storage_backend": item.storage_backend,
                "object_key": item.object_key,
                "file_format": item.file_format,
                "size_bytes": item.size_bytes,
                "file_size_mb": item.file_size_mb,
                "content_type": item.content_type,
                "created_at": item.created_at.isoformat(),
            }
            for item in run.generated_files
        ],
        "issue_manifest": [
            {
                "id": item.id,
                "issue_type": item.issue_type,
                "issue_count": item.issue_count,
                "issue_percentage": item.issue_percentage,
                "created_at": item.created_at.isoformat(),
            }
            for item in run.issue_manifests
        ],
        "validation_results": [
            {
                "id": item.id,
                "validation_name": item.validation_name,
                "status": item.status,
                "quality_score": item.quality_score,
                "expected_value": item.expected_value,
                "actual_value": item.actual_value,
                "created_at": item.created_at.isoformat(),
            }
            for item in run.validation_results
        ],
        "scenario_reports": _scenario_reports_for_run(run.id),
    }


@router.delete("/runs/{run_id}", response_model=DeleteRunsResponse, dependencies=[Depends(require_api_key)])
def delete_run(run_id: str, db: Session = Depends(get_db)) -> dict:
    deleted_ids = _delete_runs(db, [run_id])
    db.commit()
    if not deleted_ids:
        raise ValueError(f"Run not found: {run_id}")
    return {"deleted": len(deleted_ids), "requested": 1, "run_ids": deleted_ids}


@router.post("/runs/delete", response_model=DeleteRunsResponse, dependencies=[Depends(require_api_key)])
def delete_runs(payload: DeleteRunsRequest, db: Session = Depends(get_db)) -> dict:
    deleted_ids = _delete_runs(db, payload.run_ids)
    db.commit()
    return {"deleted": len(deleted_ids), "requested": len(payload.run_ids), "run_ids": deleted_ids}


def _run_summary(run) -> dict:
    summary = RunSummary.model_validate(run, from_attributes=True).model_dump()
    quality_scores = [item.quality_score for item in run.validation_results if item.quality_score is not None]
    summary["quality_score"] = quality_scores[0] if quality_scores else None
    summary.update(_scenario_summary_fields(run.id))
    return summary


def _template_payload(template) -> dict:
    failure_plan = json.loads(template.failure_plan_json)
    compatibility = validate_template_compatibility({"scenario_id": template.scenario_id, "failure_plan": failure_plan})
    return {
        "id": template.id,
        "name": template.name,
        "description": template.description,
        "domain": template.domain,
        "scenario_id": template.scenario_id,
        "records": template.records,
        "output_format": template.output_format,
        "severity": template.severity,
        "seed_behavior": template.seed_behavior,
        "failure_plan": failure_plan,
        "failure_count": len(failure_plan.get("failures", [])),
        "compatibility": compatibility,
        "created_at": template.created_at.isoformat(),
        "updated_at": template.updated_at.isoformat(),
        "last_used_at": template.last_used_at.isoformat() if template.last_used_at else None,
    }


def _scenario_builder_run_summary(run) -> dict:
    base = _run_summary(run)
    reports = _scenario_reports_for_run(run.id)
    execution = reports.get("scenario_execution_report.json", {})
    config = reports.get("scenario_run_config.json", {})
    summary = summarize_ground_truth(execution)
    return {
        **base,
        "seed": config.get("seed") or (execution.get("failure_plan") or {}).get("seed"),
        "tables_generated": len(run.generated_files),
        "failure_plan": execution.get("failure_plan") or config.get("failure_plan"),
        "overlap_mode": (execution.get("failure_plan") or config.get("failure_plan") or {}).get("overlap_mode"),
        "ground_truth_summary": summary,
        "duration_seconds": (run.completed_at - run.started_at).total_seconds() if run.completed_at else None,
    }


def _scenario_summary_fields(run_id: str) -> dict:
    root = get_settings().output_dir / run_id
    definition_path = root / "scenario_definition.json"
    config_path = root / "scenario_run_config.json"
    execution_path = root / "scenario_execution_report.json"
    if not definition_path.exists():
        return {
            "scenario_id": None,
            "scenario_name": None,
            "scenario_outcome": None,
            "scenario_severity": None,
            "scenario_variations": [],
        }
    definition = json.loads(definition_path.read_text(encoding="utf-8"))
    config = json.loads(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
    execution = json.loads(execution_path.read_text(encoding="utf-8")) if execution_path.exists() else {}
    return {
        "scenario_id": definition.get("scenario_id"),
        "scenario_name": definition.get("name") or definition.get("scenario_name"),
        "scenario_outcome": execution.get("scenario_outcome"),
        "scenario_severity": config.get("severity"),
        "scenario_variations": config.get("variation_ids") or [],
    }


def _delete_runs(db: Session, run_ids: list[str]) -> list[str]:
    storage = get_storage_service()
    repo = DatasetRunRepository(db)
    deleted_ids: list[str] = []
    for run_id in dict.fromkeys(run_ids):
        run = repo.get(run_id)
        if not run:
            continue
        for generated_file in run.generated_files:
            try:
                storage.delete_generated_file(generated_file)
            except ValueError:
                pass
        db.execute(update(GenerationJob).where(GenerationJob.run_id == run.id).values(run_id=None))
        db.delete(run)
        deleted_ids.append(run.id)
    return deleted_ids


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
def get_job(job_id: str, db: Session = Depends(get_db), _: None = Depends(require_api_key)) -> dict:
    job = GenerationJobRepository(db).get(job_id)
    if not job:
        raise ValueError(f"Generation job not found: {job_id}")
    run_detail = get_run(job.run_id, db, None) if job.run_id else None
    return {
        "job_id": job.id,
        "status": job.status,
        "run_id": job.run_id,
        "error_message": job.error_message,
        "queued_at": job.queued_at.isoformat(),
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "run": run_detail,
    }


@router.get("/runs/{run_id}/files/{file_id}/download", dependencies=[Depends(require_api_key)])
def download_generated_file(run_id: str, file_id: str, db: Session = Depends(get_db)) -> Response:
    generated_file = GeneratedFileRepository(db).get_for_run(run_id=run_id, file_id=file_id)
    if not generated_file:
        raise ValueError(f"Generated file not found for run: {run_id}")
    return get_storage_service().download_response(generated_file)


@router.get("/runs/{run_id}/download", dependencies=[Depends(require_api_key)])
def download_run_files(run_id: str, db: Session = Depends(get_db)) -> Response:
    run = DatasetRunRepository(db).get(run_id)
    if not run:
        raise ValueError(f"Run not found: {run_id}")
    if not run.generated_files:
        raise ValueError(f"No generated files are available for run: {run_id}")

    storage = get_storage_service()
    if not isinstance(storage, LocalStorageService):
        raise ValueError("Run ZIP downloads are currently available for local generated files only")

    temp_file = tempfile.NamedTemporaryFile(prefix=f"dataforge-{run_id}-", suffix=".zip", delete=False)
    temp_path = Path(temp_file.name)
    temp_file.close()

    try:
        with zipfile.ZipFile(temp_path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
            for generated_file in run.generated_files:
                source = storage.resolve_path(generated_file)
                archive.write(source, arcname=f"data/{generated_file.file_name}")
            for report_name, payload in _run_download_reports(run).items():
                archive.writestr(f"reports/{report_name}", json.dumps(payload, indent=2, default=str))
            _write_schema_version_files(archive, run)
            archive.writestr("README.md", _run_download_readme(run))
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise

    return FileResponse(
        path=temp_path,
        filename=f"dataforge-{run.domain}-{run_id}.zip",
        media_type="application/zip",
        background=BackgroundTask(temp_path.unlink, missing_ok=True),
    )


def _run_download_reports(run) -> dict[str, dict]:
    reports = {
        "validation_report.json": _validation_report_payload(run),
        "issue_manifest.json": _issue_manifest_payload(run),
        "run_summary.json": _run_summary_payload(run),
    }
    report_aliases = {
        "alignment_report.json": "alignment_report.json",
        "realism_report.json": "realism_report.json",
        "scenario_definition.json": "scenario_definition.json",
        "scenario_run_config.json": "scenario_run_config.json",
        "scenario_execution_report.json": "scenario_execution_report.json",
        "expected_validations.json": "expected_validations.json",
        "generation_retry_report.json": "generation_retry_report.json",
        "schema_diff.json": "reports/schema_diff.json",
    }
    for report_name, relative_path in report_aliases.items():
        report_path = get_settings().output_dir / run.id / relative_path
        if report_path.exists():
            reports[report_name] = json.loads(report_path.read_text(encoding="utf-8"))
    try:
        reports["ground_truth.json"] = _ground_truth_payload_for_run(run)
        reports["dataset_manifest.json"] = _dataset_manifest_for_run(run)
    except ValueError:
        pass
    return reports


def _run_summary_payload(run) -> dict:
    report_files = [
        "reports/validation_report.json",
        "reports/issue_manifest.json",
        "reports/run_summary.json",
    ]
    for report_name in ("alignment_report.json", "realism_report.json", "scenario_definition.json", "scenario_run_config.json", "scenario_execution_report.json", "expected_validations.json", "generation_retry_report.json", "schema_diff.json"):
        if (get_settings().output_dir / run.id / report_name).exists() or (get_settings().output_dir / run.id / "reports" / report_name).exists():
            report_files.append(f"reports/{report_name}")
    if _scenario_reports_for_run(run.id).get("scenario_execution_report.json", {}).get("ground_truth") is not None:
        report_files.extend(["reports/ground_truth.json", "reports/dataset_manifest.json"])
    return {
        **_run_summary(run),
        "run_id": run.id,
        "generated_tables": [
            {
                "file_name": item.file_name,
                "format": item.file_format,
                "size_bytes": item.size_bytes,
                "size_mb": item.file_size_mb,
            }
            for item in run.generated_files
        ],
        "report_files": report_files,
        "data_directory": "data/",
    }


def _issue_manifest_payload(run) -> dict:
    issues = [
        {
            "issue_type": item.issue_type,
            "count": item.issue_count,
            "configured_percentage": item.issue_percentage,
            "note": _issue_manifest_note(item.issue_type),
        }
        for item in run.issue_manifests
    ]
    return {
        "run_id": run.id,
        "domain": run.domain,
        "total_issue_types": len(issues),
        "total_injected": sum(issue["count"] for issue in issues),
        "issues": issues,
    }


def _validation_report_payload(run) -> dict:
    checks = []
    for item in run.validation_results:
        expected = _json_or_text(item.expected_value)
        actual = _json_or_text(item.actual_value)
        checks.append(
            {
                "name": item.validation_name,
                "status": item.status,
                "quality_score": item.quality_score,
                "table": expected.get("table") if isinstance(expected, dict) else None,
                "column": expected.get("column") if isinstance(expected, dict) else None,
                "expected": expected.get("expected") if isinstance(expected, dict) else expected,
                "actual": actual.get("actual") if isinstance(actual, dict) else actual,
                "failures": actual.get("failures") if isinstance(actual, dict) else None,
                "message": expected.get("message") if isinstance(expected, dict) else None,
            }
        )
    passed = sum(1 for check in checks if check["status"] == "PASS")
    failed = len(checks) - passed
    quality_score = next((check["quality_score"] for check in checks if check["quality_score"] is not None), 100)
    status = "PASS" if failed == 0 and int(quality_score) >= 80 else "FAIL"
    return {
        "run_id": run.id,
        "domain": run.domain,
        "load_type": run.load_type,
        "format": run.format,
        "record_count": run.record_count,
        "quality_score": quality_score,
        "status": status,
        "summary": {"total_checks": len(checks), "passed": passed, "failed": failed},
        "issues": [{"type": check["name"], "count": check["failures"] or 1} for check in checks if check["status"] != "PASS"],
        "checks": checks,
        "generated_at": (run.completed_at or run.started_at).isoformat(),
    }


def _run_download_readme(run) -> str:
    issue_lines = [
        f"- {item.issue_type}: {item.issue_count} affected value(s), configured {item.issue_percentage}%"
        for item in run.issue_manifests
    ]
    table_lines = [f"- data/{item.file_name} ({item.file_format}, {item.file_size_mb:.3f} MB)" for item in run.generated_files]
    scenario_definition_path = get_settings().output_dir / run.id / "scenario_definition.json"
    scenario_definition = json.loads(scenario_definition_path.read_text(encoding="utf-8")) if scenario_definition_path.exists() else None
    scenario_lines = []
    if scenario_definition:
        scenario_lines = [
            "## Scenario",
            "",
            f"- Scenario: {scenario_definition.get('name')}",
            f"- Business Problem: {scenario_definition.get('business_problem')}",
            f"- Technical Failure: {scenario_definition.get('technical_problem')}",
            f"- Expected Validations: {', '.join(scenario_definition.get('expected_validations', []))}",
            f"- Success Criteria: {'; '.join(scenario_definition.get('success_criteria', []))}",
            f"- Expected Downstream Behavior: {scenario_definition.get('expected_pipeline_behavior')}",
            "",
        ]
    return "\n".join(
        [
            f"# DataForge {run.domain.title()} Run",
            "",
            "This ZIP contains generated data files plus reports that explain validation results and intentionally injected failures.",
            "",
            "## Run Summary",
            "",
            f"- Run ID: {run.id}",
            f"- Domain: {run.domain}",
            f"- Load Type: {run.load_type}",
            f"- Format: {run.format}",
            f"- Requested Records: {run.record_count}",
            "- Realism Profile: realistic",
            f"- Generated At: {(run.completed_at or run.started_at).isoformat()}",
            "",
            "## Data Files",
            "",
            *(table_lines or ["- No data files were stored for this run."]),
            "",
            "## Reports",
            "",
            "- reports/validation_report.json: standardized validation checks and quality score.",
            "- reports/issue_manifest.json: intentionally injected issue counts and configured rates.",
            "- reports/run_summary.json: machine-readable package summary.",
            "- reports/alignment_report.json: row-count, column-order, and alignment reconciliation when available.",
            "- reports/realism_report.json: realism profile, source references, and derived rule metadata when available.",
            "- reports/ground_truth.json: benchmarkable expected failures for Scenario Builder runs when available.",
            "- reports/dataset_manifest.json: generated dataset and ground-truth artifact metadata when available.",
            "",
            "## Realism / Source Safety",
            "",
            "- Profile used: realistic",
            "- Calibration uses synthetic distributions, ranges, correlations, and business rules.",
            "- No public/reference dataset rows are copied into generated files.",
            "",
            *scenario_lines,
            "## Selected Failure Injections",
            "",
            *(issue_lines or ["- None. This is a clean generated dataset."]),
            "",
            "If validation fails, that can be expected when failure injections were selected.",
            "",
        ]
    )


def _json_or_text(value: str | None):
    if value is None:
        return None
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return value


def _issue_manifest_note(issue_type: str) -> str:
    if issue_type.startswith("schema_drift"):
        return "Schema-level drift; row percentage may not be meaningful."
    if issue_type in {"foreign_key_break", "fk_break"}:
        return "Foreign keys were intentionally changed on a controlled sample of rows."
    if issue_type == "duplicate_records":
        return "Rows were duplicated according to the configured duplicate rate."
    return "Issue was intentionally injected for validation testing."


def _write_schema_version_files(archive: zipfile.ZipFile, run) -> None:
    root = get_settings().output_dir / run.id / "schema_versions"
    if not root.exists():
        return
    for path in root.rglob("*"):
        if path.is_file():
            archive.write(path, arcname=path.relative_to(get_settings().output_dir / run.id).as_posix())


@router.get("/runs/{run_id}/files/{file_id}/preview", dependencies=[Depends(require_api_key)])
def preview_file(run_id: str, file_id: str, rows: int = Query(default=50, ge=1, le=100), db: Session = Depends(get_db)) -> dict:
    generated_file = GeneratedFileRepository(db).get_for_run(run_id=run_id, file_id=file_id)
    if not generated_file:
        raise ValueError(f"Generated file not found for run: {run_id}")
    return preview_generated_file(generated_file, get_storage_service(), max_rows=rows)


@router.get("/admin/analytics/overview", dependencies=[Depends(require_api_key)])
def analytics_overview(db: Session = Depends(get_db)) -> dict:
    return AnalyticsService(db).overview()


@router.get("/admin/analytics/domains", dependencies=[Depends(require_api_key)])
def analytics_domains(db: Session = Depends(get_db)) -> dict[str, int]:
    return AnalyticsService(db).domains()


@router.get("/admin/analytics/formats", dependencies=[Depends(require_api_key)])
def analytics_formats(db: Session = Depends(get_db)) -> dict[str, int]:
    return AnalyticsService(db).formats()


@router.get("/admin/analytics/load-types", dependencies=[Depends(require_api_key)])
def analytics_load_types(db: Session = Depends(get_db)) -> dict[str, int]:
    return AnalyticsService(db).load_types()


@router.get("/admin/analytics/quality/domains", dependencies=[Depends(require_api_key)])
def analytics_quality_domains(db: Session = Depends(get_db)) -> dict[str, float]:
    return AnalyticsService(db).quality_by_domain()


@router.get("/admin/analytics/quality/load-types", dependencies=[Depends(require_api_key)])
def analytics_quality_load_types(db: Session = Depends(get_db)) -> dict[str, float]:
    return AnalyticsService(db).quality_by_load_type()


@router.get("/admin/analytics/quality/trends", dependencies=[Depends(require_api_key)])
def analytics_quality_trends(db: Session = Depends(get_db)) -> list[dict]:
    return AnalyticsService(db).quality_trends()


@router.get("/admin/analytics/quality/lowest-runs", dependencies=[Depends(require_api_key)])
def analytics_lowest_quality_runs(db: Session = Depends(get_db)) -> list[dict]:
    return AnalyticsService(db).ranked_quality_runs(lowest=True)


@router.get("/admin/analytics/quality/highest-runs", dependencies=[Depends(require_api_key)])
def analytics_highest_quality_runs(db: Session = Depends(get_db)) -> list[dict]:
    return AnalyticsService(db).ranked_quality_runs(lowest=False)
