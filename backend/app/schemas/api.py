from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    domain: str
    load_type: str = "bulk"
    format: str = Field(default="csv", pattern="^(csv|json|parquet)$")
    records: int = Field(default=1000, ge=1)
    user_email: str = "anonymous@dataforge.local"


class GenerateResponse(BaseModel):
    run_id: str
    status: str


class ValidateRequest(BaseModel):
    run_id: str


class RunSummary(BaseModel):
    id: str
    domain: str
    load_type: str
    format: str
    record_count: int
    status: str
    started_at: datetime
    completed_at: datetime | None


class PaginatedRuns(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[RunSummary]


class RunDetail(RunSummary):
    generated_files: list[dict[str, Any]]
    issue_manifest: list[dict[str, Any]]
    validation_results: list[dict[str, Any]]
