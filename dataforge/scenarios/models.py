from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

ScenarioMode = Literal["batch", "streaming", "both"]
Severity = Literal["low", "medium", "high", "stress"]


class ScenarioReference(BaseModel):
    reference_name: str
    publisher: str
    url: str
    date_reviewed: str
    license_status_note: str
    derived_rule: str
    no_copied_rows: bool = True


class FailureSpecification(BaseModel):
    failure_id: str
    issue_type: str
    table: str | None = None
    column: str | None = None
    event_type: str | None = None
    mutation_strategy: str
    eligible_row_filter: str = "deterministic eligible records from selected tables"
    requested_rate: float = Field(default=0.03, ge=0, le=0.10)
    requested_count: int | None = Field(default=None, ge=0)
    minimum_affected: int = Field(default=1, ge=0)
    maximum_affected: int | None = Field(default=None, ge=1)
    deterministic_selector: str = "seeded_sample_without_replacement"
    seed_offset: int = 0
    severity: Severity = "medium"
    dependency_order: int = 1
    incompatible_with: list[str] = Field(default_factory=list)
    expected_validation_id: str
    expected_detected_count_rule: str = "detected_count >= selected_row_count"
    user_overridable_fields: list[str] = Field(default_factory=lambda: ["requested_rate", "requested_count", "severity"])


class ScenarioVariation(BaseModel):
    variation_id: str
    name: str
    description: str
    configuration_overrides: dict[str, Any] = Field(default_factory=dict)
    expected_validation_differences: list[str] = Field(default_factory=list)
    supported_modes: list[ScenarioMode] = Field(default_factory=lambda: ["batch"])
    recommended_severity: Severity = "medium"


class ScenarioDefinition(BaseModel):
    scenario_id: str
    version: str = "1.0.0"
    name: str
    slug: str
    domain: str
    category: str
    subcategory: str
    short_description: str
    detailed_description: str
    business_problem: str
    technical_problem: str
    intended_users: list[str]
    supported_modes: list[ScenarioMode]
    default_mode: Literal["batch", "streaming"]
    supported_output_formats: list[str]
    recommended_realism_profiles: list[str]
    default_realism_profile: str
    primary_transaction_table: str
    affected_tables: list[str]
    affected_columns: list[str] = Field(default_factory=list)
    affected_event_types: list[str] = Field(default_factory=list)
    required_tables: list[str]
    prerequisite_entities: list[str] = Field(default_factory=list)
    failure_injections: list[FailureSpecification]
    expected_validations: list[str]
    expected_quality_status: Literal["PASS", "FAIL", "PARTIAL"] = "FAIL"
    expected_pipeline_behavior: str
    success_criteria: list[str]
    failure_criteria: list[str]
    recommended_record_counts: list[int] = Field(default_factory=lambda: [100, 10_000, 100_000])
    minimum_record_count: int = Field(default=1, ge=0)
    default_record_count: int = Field(default=10_000, ge=0)
    severity_levels: list[Severity] = Field(default_factory=lambda: ["low", "medium", "high", "stress"])
    default_severity: Severity = "medium"
    supported_variations: list[ScenarioVariation]
    configurable_parameters: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)
    natural_language_examples: list[str] = Field(default_factory=list)
    references: list[ScenarioReference] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).date().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).date().isoformat())


class ScenarioRunConfig(BaseModel):
    scenario_id: str
    scenario_version: str | None = None
    domain: str | None = None
    mode: Literal["batch", "streaming"] | None = None
    realism_profile: str | None = None
    records: int | None = Field(default=None, ge=0)
    event_rate: int | None = Field(default=None, ge=1)
    duration_seconds: int | None = Field(default=None, ge=1)
    output_format: str | None = None
    database_type: str | None = None
    seed: int = 42
    severity: Severity | None = None
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

    @model_validator(mode="after")
    def validate_database_output(self) -> "ScenarioRunConfig":
        if self.output_format != "database" and self.database_type:
            raise ValueError("database_type is only valid when output_format is database")
        return self


class ScenarioValidationResult(BaseModel):
    status: Literal["PASS", "FAIL"]
    resolved_config: ScenarioRunConfig | None = None
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def scenario_to_dict(definition: ScenarioDefinition) -> dict[str, Any]:
    return definition.model_dump()

