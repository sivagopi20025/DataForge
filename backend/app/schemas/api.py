from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, HttpUrl, model_validator

from backend.app.core.config import get_settings


class GenerateRequest(BaseModel):
    domain: str
    load_type: str = "bulk"
    format: str = Field(default="csv", pattern="^(csv|json|parquet|database)$")
    database_type: str | None = Field(default=None, pattern="^(postgresql|mssql|mysql)$")
    records: int = Field(default=1000, ge=0)
    selected_tables: list[str] | None = None
    issues: dict[str, float] = Field(default_factory=dict)
    user_email: str = "anonymous@dataforge.local"
    scenario_id: str | None = None
    scenario_run_config: dict[str, Any] | None = None
    scenario_definition: dict[str, Any] | None = None
    scenario_execution_report: dict[str, Any] | None = None
    expected_validations: dict[str, Any] | None = None
    failure_plan: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_database_type(self) -> "GenerateRequest":
        if self.format == "database" and not self.database_type:
            raise ValueError("database_type is required when format is database")
        if self.format != "database" and self.database_type:
            raise ValueError("database_type is only supported when format is database")
        max_records = get_settings().max_batch_records
        if self.records > max_records:
            raise ValueError(f"records must be less than or equal to {max_records}")
        return self


class GenerateResponse(BaseModel):
    job_id: str
    status: str
    run_id: str | None = None


class ValidateRequest(BaseModel):
    run_id: str


class DeleteRunsRequest(BaseModel):
    run_ids: list[str] = Field(default_factory=list, min_length=1)


class DeleteRunsResponse(BaseModel):
    deleted: int
    requested: int
    run_ids: list[str]


class StreamStartRequest(BaseModel):
    domain: str
    event_types: list[str] = Field(default_factory=list, min_length=1)
    events_per_second: int = Field(default=1, ge=1, le=100)
    duration_minutes: int = Field(default=1, ge=1, le=240)
    format: str = Field(default="json", pattern="^json$")
    seed: int = 42
    failure_injections: dict[str, float | bool | int] = Field(default_factory=dict)
    webhook_url: HttpUrl | None = None
    webhook_secret: str | None = Field(default=None, min_length=1)
    scenario_id: str | None = None
    scenario_run_config: dict[str, Any] | None = None
    scenario_definition: dict[str, Any] | None = None


class StreamStartResponse(BaseModel):
    stream_id: str
    status: str
    domain: str
    started_at: datetime
    estimated_end_at: datetime
    events_per_second: int
    duration_minutes: int
    pull_url: str | None = None
    sse_url: str | None = None
    latest_url: str | None = None
    event_type_urls: dict[str, str] = Field(default_factory=dict)
    stream_token: str | None = None
    stream_token_expires_at: datetime | None = None


class StreamStatusResponse(BaseModel):
    stream_id: str
    domain: str
    status: str
    events_generated: int
    events_failed: int
    started_at: datetime
    estimated_end_at: datetime
    completed_at: datetime | None
    failure_summary: dict[str, int]
    webhook_delivery_summary: dict[str, Any] = Field(default_factory=dict)


class StreamEventsResponse(BaseModel):
    stream_id: str
    total: int
    events: list[dict[str, Any]]


class RunSummary(BaseModel):
    id: str
    domain: str
    load_type: str
    format: str
    record_count: int
    status: str
    quality_score: int | None = None
    started_at: datetime
    completed_at: datetime | None
    scenario_id: str | None = None
    scenario_name: str | None = None
    scenario_outcome: str | None = None
    scenario_severity: str | None = None
    scenario_variations: list[str] = Field(default_factory=list)


class PaginatedRuns(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[RunSummary]


class RunDetail(RunSummary):
    generated_files: list[dict[str, Any]]
    issue_manifest: list[dict[str, Any]]
    validation_results: list[dict[str, Any]]
    scenario_reports: dict[str, Any] = Field(default_factory=dict)


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    run_id: str | None
    error_message: str | None
    queued_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    run: RunDetail | None = None


class ScenarioConfigRequest(BaseModel):
    scenario_id: str
    scenario_version: str | None = None
    domain: str | None = None
    mode: str | None = None
    realism_profile: str | None = None
    records: int | None = Field(default=None, ge=0)
    event_rate: int | None = Field(default=None, ge=1)
    duration_seconds: int | None = Field(default=None, ge=1)
    output_format: str | None = None
    database_type: str | None = None
    seed: int = 42
    severity: str | None = None
    variation_ids: list[str] = Field(default_factory=list)
    failure_overrides: dict[str, dict[str, Any]] = Field(default_factory=dict)
    table_selection: list[str] | None = None
    event_type_selection: list[str] | None = None
    include_clean_baseline: bool = True
    include_failed_record_samples: bool = False
    generate_reports: bool = True
    requested_by: str = "anonymous@dataforge.local"
    source_text: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    warnings: list[str] = Field(default_factory=list)


class ScenarioBuilderGenerateRequest(BaseModel):
    scenario_id: str
    records: int = Field(default=10_000, ge=0)
    output_format: str = Field(default="csv", pattern="^(csv|json|parquet)$")
    seed: int = Field(default=42, ge=0)
    severity: str = "medium"
    failure_plan: dict[str, Any]
    requested_by: str = "anonymous@dataforge.local"


class ScenarioTemplateCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    scenario_id: str
    records: int = Field(default=10_000, ge=0)
    output_format: str = Field(default="csv", pattern="^(csv|json|parquet)$")
    severity: str = "medium"
    seed_behavior: str = Field(default="fixed_seed", pattern="^(fixed_seed|new_seed_each_run)$")
    failure_plan: dict[str, Any]


class ScenarioTemplateUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    records: int | None = Field(default=None, ge=0)
    output_format: str | None = Field(default=None, pattern="^(csv|json|parquet)$")
    severity: str | None = None
    seed_behavior: str | None = Field(default=None, pattern="^(fixed_seed|new_seed_each_run)$")
    failure_plan: dict[str, Any] | None = None


class ScenarioRunCompareRequest(BaseModel):
    left_run_id: str
    right_run_id: str


class DetectorOutputSubmitRequest(BaseModel):
    run_id: str
    detector_name: str = Field(min_length=1, max_length=255)
    detector_version: str | None = None
    detections: list[dict[str, Any]] = Field(default_factory=list)
    label_mapping: dict[str, str] = Field(default_factory=dict)


class EvaluationCreateRequest(DetectorOutputSubmitRequest):
    benchmark_id: str | None = None
    detector_output_format: str = Field(default="json", pattern="^(json|jsonl|csv|api)$")


class EvaluationImportRequest(BaseModel):
    run_id: str
    detector_name: str = Field(min_length=1, max_length=255)
    detector_version: str | None = None
    detector_output_format: str = Field(pattern="^(json|jsonl|csv)$")
    payload: str
    label_mapping: dict[str, str] = Field(default_factory=dict)
    benchmark_id: str | None = None


class BenchmarkCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    domain: str
    scenario_id: str
    scenario_template_id: str | None = None
    records: int = Field(default=10_000, ge=0)
    output_format: str = Field(default="csv", pattern="^(csv|json|parquet)$")
    seed: int = Field(default=42, ge=0)
    failure_plan: dict[str, Any]
    evaluation_unit: str = "entity"
    thresholds: dict[str, float] = Field(default_factory=dict)


class BenchmarkRunRequest(BaseModel):
    seed: int | None = Field(default=None, ge=0)
    seed_mode: str = Field(default="fixed", pattern="^(fixed|random)$")
    detector_mode: str = Field(default="manual_upload", pattern="^(manual_upload|api_submission)$")
    run_id: str | None = None
    detector_name: str | None = None
    detector_version: str | None = None
    detector_output_format: str = Field(default="json", pattern="^(json|jsonl|csv|api)$")
    detections: list[dict[str, Any]] = Field(default_factory=list)
    label_mapping: dict[str, str] = Field(default_factory=dict)


class BenchmarkRunDetectorSubmissionRequest(BaseModel):
    detector_name: str = Field(min_length=1, max_length=255)
    detector_version: str | None = None
    detector_output_format: str = Field(default="json", pattern="^(json|jsonl|csv|api)$")
    detections: list[dict[str, Any]] = Field(default_factory=list)
    label_mapping: dict[str, str] = Field(default_factory=dict)
    replace_existing: bool = False
