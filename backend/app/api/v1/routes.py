from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.analytics import AnalyticsService
from backend.app.db.session import get_db
from backend.app.repositories import DatasetRunRepository
from backend.app.schemas.api import GenerateRequest, GenerateResponse, PaginatedRuns, RunDetail, RunSummary, ValidateRequest
from backend.app.services.generation import DatasetGenerationService
from backend.app.services.validation import ValidationService

router = APIRouter(prefix="/api/v1")


@router.post("/generate", response_model=GenerateResponse)
def generate_dataset(payload: GenerateRequest, db: Session = Depends(get_db)) -> dict[str, str]:
    return DatasetGenerationService(db).generate(payload)


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
