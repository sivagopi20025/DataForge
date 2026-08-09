from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


CanonicalSeverity = Literal["low", "medium", "high", "critical", "stress"]
CanonicalRealism = Literal["basic", "realistic", "high", "stress"]
CanonicalDifficulty = Literal["easy", "medium", "hard", "expert"]
ScenarioStatus = Literal["draft", "candidate", "specification_only", "implemented", "reference_implemented", "deprecated", "rejected"]
ScenarioTier = Literal["A", "B", "C", "Reject"]
ImplementationReadiness = Literal[
    "ready_now",
    "needs_primitive",
    "needs_validator",
    "needs_columns",
    "needs_table",
    "needs_multiple_dependencies",
    "needs_primitive_implementation",
    "needs_validator_implementation",
    "needs_primitive_and_validator",
    "needs_schema_and_primitive",
    "needs_schema_and_validator",
    "needs_schema_primitive_validator",
    "needs_primitive_parameter_support",
    "needs_custom_logic",
]
TableSupportStatus = Literal["fully_supported", "requires_new_columns", "requires_new_table", "partially_supported"]


class ScenarioScore(BaseModel):
    business_realism_score: int = Field(ge=0, le=5)
    data_model_fit_score: int = Field(ge=0, le=5)
    enterprise_relevance_score: int = Field(ge=0, le=5)
    detection_complexity_score: int = Field(ge=0, le=5)
    demo_value_score: int = Field(ge=0, le=5)
    training_value_score: int = Field(ge=0, le=5)
    total_score: int = Field(ge=0, le=30)
    tier: ScenarioTier

    @model_validator(mode="after")
    def validate_total_and_tier(self) -> "ScenarioScore":
        expected_total = (
            self.business_realism_score
            + self.data_model_fit_score
            + self.enterprise_relevance_score
            + self.detection_complexity_score
            + self.demo_value_score
            + self.training_value_score
        )
        if self.total_score != expected_total:
            raise ValueError(f"total_score must equal component sum {expected_total}")
        expected_tier = "A" if expected_total >= 25 else "B" if expected_total >= 19 else "C" if expected_total >= 13 else "Reject"
        if self.tier != expected_tier:
            raise ValueError(f"tier must be {expected_tier} for total_score {expected_total}")
        return self


class ImplementationDependencies(BaseModel):
    tables: list[str] = Field(default_factory=list)
    columns: list[str] = Field(default_factory=list)
    primitives: list[str] = Field(default_factory=list)
    validators: list[str] = Field(default_factory=list)
    unsupported_parameters: list[str] = Field(default_factory=list)
    custom_logic: bool = False

    @property
    def has_dependencies(self) -> bool:
        return bool(self.tables or self.columns or self.primitives or self.validators or self.unsupported_parameters or self.custom_logic)


class MasterScenarioMetadata(BaseModel):
    """Canonical scenario metadata for future configuration-driven catalogs.

    This model intentionally mirrors the existing ScenarioDefinition shape only where needed.
    It is the stable, training-ready metadata contract that lets DataForge scale scenario
    definitions without hardcoding hundreds of Python branches.
    """

    scenario_id: str
    domain: str
    business_process: str
    entity: str
    scenario_name: str
    description: str
    failure_category: str
    failure_primitive: str
    primitive_parameters: dict[str, Any] = Field(default_factory=dict)
    primary_table: str
    related_tables: list[str] = Field(default_factory=list)
    required_columns: list[str] = Field(default_factory=list)
    business_rule: str
    mutation_strategy: str
    validator: str
    validator_pattern: str
    validator_parameters: dict[str, Any] = Field(default_factory=dict)
    expected_evidence: list[str] = Field(default_factory=list)
    severity: CanonicalSeverity = "medium"
    realism: CanonicalRealism = "realistic"
    difficulty: CanonicalDifficulty = "medium"
    tags: list[str] = Field(default_factory=list)
    training_value: str = "Teaches data quality, validation, and pipeline-recovery behavior for a realistic enterprise workflow."
    status: ScenarioStatus = "implemented"
    version: str = "1.0.0"
    score: ScenarioScore | None = None
    implementation_readiness: ImplementationReadiness = "ready_now"
    implementation_dependencies: ImplementationDependencies = Field(default_factory=ImplementationDependencies)
    execution_status: Literal["specification_only", "ready", "executable", "custom_reference", "deprecated", "rejected"] = "specification_only"
    table_support_status: TableSupportStatus = "fully_supported"
    proposed_tables: list[str] = Field(default_factory=list)
    proposed_columns: list[str] = Field(default_factory=list)
    rejected_reason: str | None = None

    @model_validator(mode="after")
    def validate_required_shape(self) -> "MasterScenarioMetadata":
        if self.primary_table not in self.related_tables:
            self.related_tables = [self.primary_table, *self.related_tables]
        self.related_tables = sorted(dict.fromkeys(self.related_tables))
        self.required_columns = sorted(dict.fromkeys(self.required_columns))
        self.expected_evidence = sorted(dict.fromkeys(self.expected_evidence))
        self.tags = sorted(dict.fromkeys(self.tags))
        return self
