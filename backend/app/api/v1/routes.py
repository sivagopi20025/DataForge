from __future__ import annotations

import tempfile
import zipfile
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from fastapi.responses import FileResponse, Response
from starlette.background import BackgroundTask
from sqlalchemy.orm import Session

from backend.app.analytics import AnalyticsService
from backend.app.core.config import get_settings
from backend.app.core.security import require_api_key
from backend.app.db.session import get_db
from backend.app.repositories import DatasetRunRepository, GeneratedFileRepository, GenerationJobRepository
from backend.app.schemas.api import GenerateRequest, GenerateResponse, JobStatusResponse, PaginatedRuns, RunDetail, RunSummary, ValidateRequest
from backend.app.services.file_preview import preview_generated_file
from backend.app.services.jobs import GenerationJobService, run_generation_job
from backend.app.services.retention import cleanup_expired_run_history
from backend.app.services.storage import LocalStorageService, get_storage_service
from dataforge.domains import DOMAIN_SPECS
from backend.app.services.validation import ValidationService

router = APIRouter(prefix="/api/v1")


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


@router.post("/validate", dependencies=[Depends(require_api_key)])
def validate_dataset(payload: ValidateRequest, db: Session = Depends(get_db)) -> dict:
    return ValidationService(db).validate_run(payload.run_id)


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
        "items": [RunSummary.model_validate(run, from_attributes=True).model_dump() for run in runs],
    }


@router.get("/runs/{run_id}", response_model=RunDetail)
def get_run(run_id: str, db: Session = Depends(get_db), _: None = Depends(require_api_key)) -> dict:
    run = DatasetRunRepository(db).get(run_id)
    if not run:
        raise ValueError(f"Run not found: {run_id}")
    return {
        **RunSummary.model_validate(run, from_attributes=True).model_dump(),
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
    }


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
                archive.write(source, arcname=generated_file.file_name)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise

    return FileResponse(
        path=temp_path,
        filename=f"dataforge-{run.domain}-{run_id}.zip",
        media_type="application/zip",
        background=BackgroundTask(temp_path.unlink, missing_ok=True),
    )


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
