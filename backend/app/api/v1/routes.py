from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.app.analytics import AnalyticsService
from backend.app.core.config import get_settings
from backend.app.db.session import get_db
from backend.app.repositories import DatasetRunRepository, GeneratedFileRepository
from backend.app.schemas.api import GenerateRequest, GenerateResponse, PaginatedRuns, RunDetail, RunSummary, ValidateRequest
from backend.app.services.generation import DatasetGenerationService
from dataforge.domains import DOMAIN_SPECS
from backend.app.services.validation import ValidationService

router = APIRouter(prefix="/api/v1")


@router.post("/generate", response_model=GenerateResponse)
def generate_dataset(payload: GenerateRequest, db: Session = Depends(get_db)) -> dict[str, str]:
    return DatasetGenerationService(db).generate(payload)


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


@router.post("/validate")
def validate_dataset(payload: ValidateRequest, db: Session = Depends(get_db)) -> dict:
    return ValidationService(db).validate_run(payload.run_id)


@router.get("/runs", response_model=PaginatedRuns)
def list_runs(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> dict:
    repo = DatasetRunRepository(db)
    runs = repo.list(limit=limit, offset=offset)
    return {
        "total": repo.count(),
        "limit": limit,
        "offset": offset,
        "items": [RunSummary.model_validate(run, from_attributes=True).model_dump() for run in runs],
    }


@router.get("/runs/{run_id}", response_model=RunDetail)
def get_run(run_id: str, db: Session = Depends(get_db)) -> dict:
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
                "file_format": item.file_format,
                "file_size_mb": item.file_size_mb,
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


@router.get("/runs/{run_id}/files/{file_id}/download")
def download_generated_file(run_id: str, file_id: str, db: Session = Depends(get_db)) -> FileResponse:
    generated_file = GeneratedFileRepository(db).get_for_run(run_id=run_id, file_id=file_id)
    if not generated_file:
        raise ValueError(f"Generated file not found for run: {run_id}")
    path = Path(generated_file.file_path).resolve()
    output_root = get_settings().output_dir.resolve()
    if not path.is_relative_to(output_root):
        raise ValueError(f"Generated file path is outside the configured output directory: {generated_file.file_name}")
    if not path.exists() or not path.is_file():
        raise ValueError(f"Generated file is no longer available: {generated_file.file_name}")
    return FileResponse(
        path=path,
        filename=generated_file.file_name,
        media_type="application/octet-stream",
    )


@router.get("/admin/analytics/overview")
def analytics_overview(db: Session = Depends(get_db)) -> dict:
    return AnalyticsService(db).overview()


@router.get("/admin/analytics/domains")
def analytics_domains(db: Session = Depends(get_db)) -> dict[str, int]:
    return AnalyticsService(db).domains()


@router.get("/admin/analytics/formats")
def analytics_formats(db: Session = Depends(get_db)) -> dict[str, int]:
    return AnalyticsService(db).formats()


@router.get("/admin/analytics/load-types")
def analytics_load_types(db: Session = Depends(get_db)) -> dict[str, int]:
    return AnalyticsService(db).load_types()


@router.get("/admin/analytics/quality/domains")
def analytics_quality_domains(db: Session = Depends(get_db)) -> dict[str, float]:
    return AnalyticsService(db).quality_by_domain()


@router.get("/admin/analytics/quality/load-types")
def analytics_quality_load_types(db: Session = Depends(get_db)) -> dict[str, float]:
    return AnalyticsService(db).quality_by_load_type()


@router.get("/admin/analytics/quality/trends")
def analytics_quality_trends(db: Session = Depends(get_db)) -> list[dict]:
    return AnalyticsService(db).quality_trends()


@router.get("/admin/analytics/quality/lowest-runs")
def analytics_lowest_quality_runs(db: Session = Depends(get_db)) -> list[dict]:
    return AnalyticsService(db).ranked_quality_runs(lowest=True)


@router.get("/admin/analytics/quality/highest-runs")
def analytics_highest_quality_runs(db: Session = Depends(get_db)) -> list[dict]:
    return AnalyticsService(db).ranked_quality_runs(lowest=False)
