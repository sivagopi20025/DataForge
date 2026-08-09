from __future__ import annotations

import copy
from collections import defaultdict
from typing import Any

from dataforge.model import Dataset, DomainSpec, FailureEvent
from dataforge.scenarios.catalog import expanded_scenario_items, load_scenario_quality_audit
from dataforge.scenarios.catalog.models import MasterScenarioMetadata
from dataforge.scenarios.configuration import (
    FailurePlan,
    FailurePlanItem,
    compatible_primitives_for_scenario,
    scenario_configuration_metadata,
    validate_failure_plan,
)
from dataforge.scenarios.primitives import PRIMITIVE_REGISTRY, PrimitiveExecutionContext, PrimitiveResult
from dataforge.scenarios.requirements import REQUIREMENT_RESOLVER
from dataforge.scenarios.schema_semantics import COLUMN_SEMANTIC_RESOLVER
from dataforge.scenarios.validator_registry import VALIDATOR_REGISTRY, ValidatorExecutionContext


FRIENDLY_PRIMITIVE_NAMES = {
    "duplicate_entity": "Duplicate Records / Entities",
    "duplicate_event": "Duplicate Events",
    "retry_burst": "Excessive Retries",
    "timeout_violation": "Processing Delay / SLA Violation",
    "timestamp_delay": "Delayed Timestamp",
    "stale_timestamp": "Stale Timestamp",
    "timestamp_out_of_order": "Out-of-order Timestamp",
    "sequence_gap": "Sequence Gap",
    "cross_table_mismatch": "Cross-table Data Mismatch",
    "aggregate_mismatch": "Aggregate / Balance Mismatch",
    "invalid_state_transition": "Invalid Status Transition",
    "policy_violation": "Business Policy Violation",
    "geographic_jump": "Impossible Location Jump",
    "value_above_threshold": "Threshold Breach",
    "value_below_threshold": "Below-threshold Value",
    "negative_numeric_value": "Negative Numeric Value",
    "availability_failure": "Availability Failure",
    "missing_entity": "Missing Entity",
    "remove_entity": "Missing Records",
    "datatype_mismatch": "Data Type Mismatch",
    "null_required_attribute": "Required Field Null",
    "set_required_value_null": "Required Field Null",
}

PRIMITIVE_VALIDATOR_DEFAULTS = {
    "duplicate_entity": "duplicate_key_validator",
    "duplicate_event": "sequence_validator",
    "retry_burst": "sequence_validator",
    "timeout_violation": "sla_validator",
    "timestamp_delay": "sla_validator",
    "stale_timestamp": "sla_validator",
    "timestamp_out_of_order": "sequence_validator",
    "sequence_gap": "sequence_validator",
    "cross_table_mismatch": "cross_table_consistency_validator",
    "aggregate_mismatch": "aggregate_balance_validator",
    "invalid_state_transition": "state_transition_validator",
    "policy_violation": "policy_validator",
    "geographic_jump": "geographic_validator",
    "value_above_threshold": "threshold_validator",
    "value_below_threshold": "threshold_validator",
    "negative_numeric_value": "range_validator",
    "availability_failure": "availability_validator",
    "missing_entity": "missing_record_validator",
    "remove_entity": "missing_record_validator",
    "datatype_mismatch": "datatype_validator",
    "null_required_attribute": "required_field_validator",
    "set_required_value_null": "required_field_validator",
}

MANUFACTURING_BATCH_9_FIELD_AUDIT = {
    "factories.planned_capacity_amount": {
        "classification": "valid_domain_field",
        "reason": "Represents factory-level planned production capacity for aggregate/capacity scenarios.",
    },
    "production_lines.risk_score": {
        "classification": "valid_domain_field",
        "reason": "Represents operational risk of a production line based on capacity and stability.",
    },
    "production_lines.idempotency_key": {
        "classification": "valid_domain_field",
        "reason": "Manufacturing execution systems often use command/event idempotency keys for retries.",
    },
    "suppliers.idempotency_key": {
        "classification": "rename_recommended",
        "reason": "Useful for supplier API sync retries, but supplier_sync_idempotency_key would be clearer later.",
    },
    "work_orders.expected_amount": {
        "classification": "rename_recommended",
        "reason": "Semantically valid as planned quantity/value, but planned_quantity already exists; future rename to expected_quantity is clearer.",
    },
    "work_orders.actual_amount": {
        "classification": "rename_recommended",
        "reason": "Semantically valid as produced quantity/value, but produced_quantity already exists; future rename to actual_quantity is clearer.",
    },
    "work_orders.risk_score": {
        "classification": "valid_domain_field",
        "reason": "Represents work-order operational risk driven by rejection/line factors.",
    },
    "work_orders.idempotency_key": {
        "classification": "valid_domain_field",
        "reason": "Work-order creation/update retries need idempotency keys in MES/API integrations.",
    },
    "quality_checks.scenario_status_code": {
        "classification": "semantic_mapping_only",
        "reason": "Currently mirrors quality result for generic status scenarios; future schema should use quality_status_code.",
    },
    "quality_checks.risk_score": {
        "classification": "valid_domain_field",
        "reason": "Quality inspection risk is a normal operational signal.",
    },
    "quality_checks.idempotency_key": {
        "classification": "valid_domain_field",
        "reason": "Inspection event ingestion can be retried and deduplicated by idempotency key.",
    },
}


def get_expanded_scenario(scenario_id: str) -> MasterScenarioMetadata:
    for item in expanded_scenario_items():
        if item.scenario_id == scenario_id:
            return item
    raise ValueError(f"Unknown scenario_id: {scenario_id}")


def primitive_display_name(primitive: str) -> str:
    return FRIENDLY_PRIMITIVE_NAMES.get(primitive, primitive.replace("_", " ").title())


def default_failure_plan_for_scenario(scenario: MasterScenarioMetadata) -> FailurePlan:
    rate = float(scenario.primitive_parameters.get("affected_rate_default", 0.03))
    return FailurePlan(
        scenario_id=scenario.scenario_id,
        seed=42,
        overlap_mode="non_overlapping",
        failures=[
            FailurePlanItem(
                primitive_id=scenario.failure_primitive,
                mode="percentage",
                value=rate,
                table=scenario.primary_table,
                column=_default_column(scenario),
            )
        ],
    )


def build_scenario_configuration(scenario_id: str, *, records: int | None = None) -> dict[str, Any]:
    scenario = get_expanded_scenario(scenario_id)
    resolution = REQUIREMENT_RESOLVER.resolve(scenario)
    if scenario.execution_status not in {"executable", "custom_reference"} or not resolution.execution_supported:
        raise ValueError("Scenario is not executable yet. Choose a V1-ready executable scenario.")
    records = int(records if records is not None else 10_000)
    quality = _quality_row(scenario.scenario_id)
    compatible = compatible_primitives_for_scenario(scenario)
    default_plan = default_failure_plan_for_scenario(scenario)
    return {
        "scenario": _scenario_overview(scenario, quality),
        "required_tables": _required_tables(scenario, records),
        "default_failure_plan": _plan_to_payload(scenario, default_plan, records),
        "compatible_primitives": [_primitive_option(scenario, primitive) for primitive in compatible],
        "parameter_schema": {
            "records": {"minimum": 0, "maximum": 500_000, "default": records},
            "failure_value_percentage": {"minimum": 0.001, "maximum": 0.10, "default": default_plan.failures[0].value},
            "failure_value_exact_count": {"minimum": 1, "maximum": records},
            "overlap_mode": {"allowed": ["non_overlapping", "allow_overlap"], "default": "non_overlapping"},
        },
        "configuration_metadata": scenario_configuration_metadata(scenario),
        "manufacturing_field_audit": MANUFACTURING_BATCH_9_FIELD_AUDIT if scenario.domain == "manufacturing" else {},
    }


def preview_failure_plan(scenario_id: str, plan: FailurePlan, *, records: int = 10_000) -> dict[str, Any]:
    scenario = get_expanded_scenario(scenario_id)
    validation = validate_failure_plan(scenario, plan)
    failures = [_failure_preview(scenario, item, records) for item in plan.failures]
    total_estimated = sum(item["estimated_affected"] for item in failures)
    if plan.overlap_mode == "non_overlapping":
        total_estimated = min(total_estimated, max(records, 0))
    warnings: list[str] = []
    if not validation["valid"]:
        warnings.extend(validation["errors"])
    if plan.overlap_mode == "non_overlapping":
        warnings.append("Non-overlap is enforced best-effort for failures targeting the same table/entity type; unrelated tables are independent.")
    if any(item.mode == "percentage" and item.value >= 0.08 for item in plan.failures):
        warnings.append("High injection percentages may make the dataset intentionally unrealistic; use Heavy settings only for stress testing.")
    if any(item.primitive in {"duplicate_entity", "retry_burst", "duplicate_event"} and item.mode == "percentage" and item.value >= 0.05 for item in plan.failures):
        warnings.append("Duplicate and retry failures can increase final row/event volume beyond the clean baseline.")
    for item, rendered in zip(plan.failures, failures):
        if item.mode == "exact_count" and int(item.value) > records:
            warnings.append(f"Exact count for {rendered['display_name']} exceeds eligible records and will be capped.")
    return {
        "scenario_id": scenario_id,
        "valid": validation["valid"],
        "errors": validation["errors"],
        "records": records,
        "overlap_mode": plan.overlap_mode,
        "failures": failures,
        "estimated_total_affected_entities": total_estimated,
        "warnings": warnings,
    }


def validate_template_compatibility(template_payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        scenario = get_expanded_scenario(str(template_payload.get("scenario_id") or ""))
        if scenario.execution_status not in {"executable", "custom_reference"}:
            errors.append("Scenario is no longer executable.")
        plan = FailurePlan.model_validate(template_payload.get("failure_plan") or {})
        validation = validate_failure_plan(scenario, plan)
        errors.extend(validation["errors"])
    except Exception as exc:
        errors.append(str(exc))
    return {"valid": not errors, "errors": errors, "warnings": warnings}


def summarize_ground_truth(report: dict[str, Any]) -> dict[str, Any]:
    rows = report.get("ground_truth") or []
    selected = sum(int(row.get("selected_count", 0)) for row in rows)
    actual = sum(int(row.get("actual_count", 0)) for row in rows)
    detected = sum(int(row.get("detected_count", 0)) for row in rows)
    return {
        "failure_count": len(rows),
        "selected_count": selected,
        "actual_count": actual,
        "detected_count": detected,
        "injection_success_rate": round(actual / selected, 4) if selected else 1.0,
        "detection_rate": round(detected / actual, 4) if actual else 1.0,
    }


def compare_scenario_runs(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    left_summary = summarize_ground_truth(left)
    right_summary = summarize_ground_truth(right)
    return {
        "left": left_summary,
        "right": right_summary,
        "delta": {
            "actual_count": right_summary["actual_count"] - left_summary["actual_count"],
            "detected_count": right_summary["detected_count"] - left_summary["detected_count"],
            "detection_rate": round(right_summary["detection_rate"] - left_summary["detection_rate"], 4),
        },
    }


def execute_failure_plan(
    dataset: Dataset,
    spec: DomainSpec,
    scenario: MasterScenarioMetadata,
    plan: FailurePlan,
    *,
    severity: str = "medium",
) -> tuple[Dataset, list[FailureEvent], dict[str, Any]]:
    validation = validate_failure_plan(scenario, plan)
    if not validation["valid"]:
        raise ValueError("; ".join(validation["errors"]))
    generated = copy.deepcopy(dataset)
    failure_events: list[FailureEvent] = []
    ground_truth: list[dict[str, Any]] = []
    assigned_by_table: dict[str, set[Any]] = defaultdict(set)
    validators: list[dict[str, Any]] = []

    for index, item in enumerate(plan.failures):
        primitive_result = _execute_primitive_with_overlap_policy(
            generated,
            spec,
            scenario,
            item,
            seed=plan.seed + item.seed_offset + index * 997,
            severity=severity,
            overlap_mode=plan.overlap_mode,
            assigned_by_table=assigned_by_table,
        )
        generated = primitive_result.dataset
        table = primitive_result.mutation_metadata.get("table") or item.table or scenario.primary_table
        column = primitive_result.mutation_metadata.get("column") or item.column
        event = primitive_result.to_failure_event(str(table), str(column) if column else None)
        failure_events.append(event)
        validator_pattern = _validator_for_failure(scenario, item.primitive)
        validator_result = VALIDATOR_REGISTRY.validate(
            validator_pattern,
            ValidatorExecutionContext(
                dataset=generated,
                spec=spec,
                parameters=_validator_parameters(scenario, item, validator_pattern),
                primitive_result=primitive_result,
                expected_count=primitive_result.actual_mutated_count,
                severity=severity,
            ),
        )
        validators.append(validator_result)
        detected = int(validator_result.get("detected_count", 0))
        ground_truth.append(
            {
                "primitive_id": item.primitive,
                "display_name": primitive_display_name(item.primitive),
                "requested": {"mode": item.mode, "value": item.value},
                "target": {"table": table, "column": column, "entity": scenario.entity},
                "expected_count": _expected_count_for_item(item, primitive_result.mutation_metadata.get("eligible_row_count", 0)),
                "selected_count": primitive_result.selected_count,
                "actual_count": primitive_result.actual_mutated_count,
                "detected_count": detected,
                "detection_rate": round(detected / primitive_result.actual_mutated_count, 4) if primitive_result.actual_mutated_count else 1.0,
                "affected_entities": primitive_result.affected_entity_ids[:100],
                "evidence": validator_result.get("evidence", {}),
                "reconciliation_status": validator_result.get("reconciliation_status", "FAIL"),
            }
        )

    report = {
        "scenario_id": scenario.scenario_id,
        "failure_plan": plan.model_dump(by_alias=True),
        "ground_truth": ground_truth,
        "scenario_validator_results": validators,
        "requested_failure_counts": {row["primitive_id"]: row["requested"] for row in ground_truth},
        "selected_target_counts": {row["primitive_id"]: row["selected_count"] for row in ground_truth},
        "actual_mutation_counts": {row["primitive_id"]: row["actual_count"] for row in ground_truth},
        "detected_issue_counts": {row["primitive_id"]: row["detected_count"] for row in ground_truth},
        "reconciliation_by_failure": {
            row["primitive_id"]: {"status": row["reconciliation_status"], "actual": row["actual_count"], "detected": row["detected_count"]}
            for row in ground_truth
        },
        "scenario_outcome": "PASS" if all(row["reconciliation_status"] == "PASS" for row in ground_truth) else "PARTIAL",
    }
    report["ground_truth_summary"] = summarize_ground_truth(report)
    return generated, failure_events, report


def _execute_primitive_with_overlap_policy(
    dataset: Dataset,
    spec: DomainSpec,
    scenario: MasterScenarioMetadata,
    item: FailurePlanItem,
    *,
    seed: int,
    severity: str,
    overlap_mode: str,
    assigned_by_table: dict[str, set[Any]],
) -> PrimitiveResult:
    params = _primitive_parameters(scenario, item, dataset)
    table = str(params.get("table") or scenario.primary_table)
    best_result: PrimitiveResult | None = None
    for attempt in range(10 if overlap_mode == "non_overlapping" else 1):
        trial_dataset = copy.deepcopy(dataset)
        result = PRIMITIVE_REGISTRY.execute(
            item.primitive,
            PrimitiveExecutionContext(dataset=trial_dataset, spec=spec, parameters=params, seed=seed + attempt * 37, severity=severity),
        )
        best_result = result
        affected = set(result.affected_entity_ids)
        if overlap_mode != "non_overlapping" or not (affected & assigned_by_table[table]):
            assigned_by_table[table].update(affected)
            return result
    if best_result is None:
        raise RuntimeError("Primitive did not return a result")
    assigned_by_table[table].update(best_result.affected_entity_ids)
    best_result.warnings.append("non_overlapping_best_effort_conflict")
    return best_result


def _primitive_parameters(scenario: MasterScenarioMetadata, item: FailurePlanItem, dataset: Dataset) -> dict[str, Any]:
    params = dict(scenario.primitive_parameters)
    params["table"] = item.table or params.get("table") or scenario.primary_table
    if item.column:
        params["column"] = item.column
    table = str(params["table"])
    eligible = len(dataset.get(table, []))
    if item.mode == "percentage":
        params["affected_rate"] = float(item.value)
    else:
        params["affected_rate"] = min(1.0, float(item.value) / max(eligible, 1))
    return COLUMN_SEMANTIC_RESOLVER.normalize_parameters(scenario.domain, table, params)


def _validator_parameters(scenario: MasterScenarioMetadata, item: FailurePlanItem, validator_pattern: str) -> dict[str, Any]:
    params = dict(scenario.validator_parameters)
    params["table"] = item.table or params.get("table") or scenario.primary_table
    if item.column:
        params["columns"] = [item.column]
    return COLUMN_SEMANTIC_RESOLVER.normalize_parameters(scenario.domain, str(params["table"]), params)


def _validator_for_failure(scenario: MasterScenarioMetadata, primitive: str) -> str:
    if primitive == scenario.failure_primitive:
        return scenario.validator_pattern
    return PRIMITIVE_VALIDATOR_DEFAULTS.get(primitive, scenario.validator_pattern)


def _scenario_overview(scenario: MasterScenarioMetadata, quality: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "scenario_id": scenario.scenario_id,
        "scenario_name": scenario.scenario_name,
        "domain": scenario.domain,
        "business_process": scenario.business_process,
        "description": scenario.description,
        "business_rule": scenario.business_rule,
        "example_failure": scenario.mutation_strategy,
        "severity": scenario.severity,
        "entity": scenario.entity,
        "failure_category": scenario.failure_category,
        "execution_status": scenario.execution_status,
        "v1_ready": bool(quality and quality.get("quality_status") == "v1_ready"),
        "quality_status": quality.get("quality_status") if quality else "unknown",
        "validator_detection_strategy": _friendly_validator_name(scenario.validator_pattern),
        "technical_details": {
            "primitive_id": scenario.failure_primitive,
            "validator_id": scenario.validator_pattern,
            "semantic_mappings": scenario.required_columns,
        },
    }


def _required_tables(scenario: MasterScenarioMetadata, records: int) -> list[dict[str, Any]]:
    tables = []
    for table in scenario.related_tables:
        role = "primary scenario table" if table == scenario.primary_table else "related validation table"
        estimate = records if table == scenario.primary_table else max(1 if records else 0, int(records * 0.35))
        tables.append({"table": table, "role": role, "estimated_rows": estimate, "business_purpose": table.replace("_", " ").title()})
    return tables


def _plan_to_payload(scenario: MasterScenarioMetadata, plan: FailurePlan, records: int) -> dict[str, Any]:
    return {
        "scenario_id": plan.scenario_id,
        "seed": plan.seed,
        "overlap_mode": plan.overlap_mode,
        "failures": [_failure_preview(scenario, item, records) for item in plan.failures],
    }


def _failure_preview(scenario: MasterScenarioMetadata, item: FailurePlanItem, records: int) -> dict[str, Any]:
    estimated = _expected_count_for_item(item, records)
    return {
        "primitive_id": item.primitive,
        "display_name": primitive_display_name(item.primitive),
        "mode": item.mode,
        "value": item.value,
        "target_table": item.table or scenario.primary_table,
        "target_column": item.column or _default_column(scenario),
        "target_entity": scenario.entity,
        "estimated_affected": estimated,
        "estimated_from_rows": records,
        "validator": _friendly_validator_name(_validator_for_failure(scenario, item.primitive)),
        "technical": {"primitive_id": item.primitive, "validator_id": _validator_for_failure(scenario, item.primitive)},
    }


def _primitive_option(scenario: MasterScenarioMetadata, primitive: str) -> dict[str, Any]:
    supported = primitive in PRIMITIVE_REGISTRY.runtime_implemented()
    return {
        "primitive_id": primitive,
        "display_name": primitive_display_name(primitive),
        "default_mode": "percentage",
        "default_value": float(scenario.primitive_parameters.get("affected_rate_default", 0.03)),
        "target_table": scenario.primary_table,
        "target_column": _default_column(scenario),
        "supported": supported,
        "unavailable_reason": None if supported else "Primitive is not runtime implemented for this scenario.",
        "validator": _friendly_validator_name(_validator_for_failure(scenario, primitive)),
    }


def _expected_count_for_item(item: FailurePlanItem, eligible_count: int) -> int:
    if eligible_count <= 0:
        return 0
    if item.mode == "exact_count":
        return min(int(item.value), eligible_count)
    return max(1, min(eligible_count, int(eligible_count * float(item.value))))


def _default_column(scenario: MasterScenarioMetadata) -> str | None:
    columns = [column for column in scenario.required_columns if not column.endswith("_id")]
    return columns[0] if columns else None


def _friendly_validator_name(validator: str) -> str:
    return validator.replace("_validator", "").replace("_", " ").title()


def _quality_row(scenario_id: str) -> dict[str, Any] | None:
    try:
        audit = load_scenario_quality_audit()
    except FileNotFoundError:
        return None
    return next((row for row in audit.get("scenarios", []) if row.get("scenario_id") == scenario_id), None)
