from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from dataforge.scenarios.catalog.models import MasterScenarioMetadata
from dataforge.scenarios.primitives import PRIMITIVE_REGISTRY


FailurePlanMode = Literal["percentage", "exact_count"]
FailurePlanOverlapMode = Literal["non_overlapping", "allow_overlap"]


class FailurePlanItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    primitive: str = Field(alias="primitive_id")
    mode: FailurePlanMode = "percentage"
    value: float = Field(gt=0)
    table: str | None = None
    column: str | None = None
    seed_offset: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_mode_value(self) -> "FailurePlanItem":
        if self.mode == "percentage" and not (0 < self.value <= 1):
            raise ValueError("percentage failure plan values must be between 0 and 1")
        if self.mode == "exact_count" and self.value < 1:
            raise ValueError("exact_count failure plan values must be at least 1")
        return self


class FailurePlan(BaseModel):
    scenario_id: str
    seed: int = Field(default=42, ge=0)
    overlap_mode: FailurePlanOverlapMode = "non_overlapping"
    failures: list[FailurePlanItem] = Field(min_length=1)


class GroundTruthRecord(BaseModel):
    scenario_id: str
    primitive: str
    table: str | None = None
    column: str | None = None
    expected_count: int = Field(ge=0)
    selected_count: int = Field(ge=0)
    actual_mutated_count: int = Field(ge=0)
    affected_entities: list[Any] = Field(default_factory=list)
    seed: int = Field(ge=0)
    reconciliation_status: Literal["PASS", "PARTIAL", "FAIL"] = "PASS"


def compatible_primitives_for_scenario(scenario: MasterScenarioMetadata) -> list[str]:
    """Return runtime primitives compatible with the scenario's current configuration.

    Batch 9 keeps this intentionally conservative: the scenario's own primitive is always
    considered compatible when runtime-backed, and primitives from the same broad failure
    category are offered only when they are already runtime implemented.
    """

    runtime = PRIMITIVE_REGISTRY.runtime_implemented()
    compatible = [scenario.failure_primitive] if scenario.failure_primitive in runtime else []
    category_hints = {
        "duplication": {"duplicate_entity", "duplicate_event", "retry_burst"},
        "retry": {"retry_burst", "duplicate_entity"},
        "temporal": {"timestamp_delay", "stale_timestamp", "timeout_violation", "timestamp_out_of_order"},
        "volume_anomaly": {"volume_spike", "volume_drop"},
        "aggregate_mismatch": {"aggregate_mismatch", "cross_table_mismatch"},
        "threshold_violation": {"value_above_threshold", "value_below_threshold", "capacity_exceeded", "negative_numeric_value"},
    }
    for primitive in sorted(category_hints.get(scenario.failure_category, set()) & runtime):
        if primitive not in compatible:
            compatible.append(primitive)
    return compatible


def scenario_configuration_metadata(scenario: MasterScenarioMetadata) -> dict[str, Any]:
    return {
        "scenario_id": scenario.scenario_id,
        "domain": scenario.domain,
        "primary_table": scenario.primary_table,
        "default_primitive": scenario.failure_primitive,
        "compatible_primitives": compatible_primitives_for_scenario(scenario),
        "configurable_fields": {
            "records": {"type": "integer", "minimum": 0, "description": "Primary transaction table record count."},
            "seed": {"type": "integer", "minimum": 0, "description": "Deterministic data and mutation selector seed."},
            "failure_plan": {"contract": "FailurePlan", "default_overlap_mode": "non_overlapping"},
        },
    }


def validate_failure_plan(scenario: MasterScenarioMetadata, plan: FailurePlan) -> dict[str, Any]:
    errors: list[str] = []
    if plan.scenario_id != scenario.scenario_id:
        errors.append("failure plan scenario_id does not match selected scenario")
    compatible = set(compatible_primitives_for_scenario(scenario))
    for item in plan.failures:
        if item.primitive not in compatible:
            errors.append(f"primitive {item.primitive} is not compatible with {scenario.scenario_id}")
    return {
        "scenario_id": scenario.scenario_id,
        "valid": not errors,
        "errors": errors,
        "overlap_mode": plan.overlap_mode,
        "compatible_primitives": sorted(compatible),
    }


def ground_truth_from_execution_result(result: Any) -> GroundTruthRecord:
    primitive = result.primitive_result
    metadata = primitive.get("mutation_metadata", {})
    return GroundTruthRecord(
        scenario_id=result.scenario_id,
        primitive=primitive.get("primitive_id", ""),
        table=metadata.get("table"),
        column=metadata.get("column"),
        expected_count=int(primitive.get("actual_mutated_count", 0)),
        selected_count=int(primitive.get("selected_count", 0)),
        actual_mutated_count=int(primitive.get("actual_mutated_count", 0)),
        affected_entities=list(primitive.get("affected_entity_ids", [])),
        seed=int(metadata.get("seed") or 0),
        reconciliation_status=result.validator_result.get("reconciliation_status", "PASS"),
    )
