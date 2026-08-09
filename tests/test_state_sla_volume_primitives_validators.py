from __future__ import annotations

from dataforge.domains.retail.schemas import RETAIL_SPEC
from dataforge.scenarios.primitives import PRIMITIVE_REGISTRY, PrimitiveExecutionContext
from dataforge.scenarios.validator_registry import VALIDATOR_REGISTRY, ValidatorExecutionContext


def _dataset() -> dict[str, list[dict]]:
    return {
        "payments": [
            {"payment_id": "P1", "sale_id": "S1", "customer_id": "C1", "amount": "10.00", "payment_type": "card", "payment_timestamp": "2026-01-01T01:00:00", "status": "pending"},
            {"payment_id": "P2", "sale_id": "S2", "customer_id": "C2", "amount": "20.00", "payment_type": "card", "payment_timestamp": "2026-01-01T02:00:00", "status": "settled"},
            {"payment_id": "P3", "sale_id": "S3", "customer_id": "C2", "amount": "30.00", "payment_type": "cash", "payment_timestamp": "2026-01-01T03:00:00", "status": "settled"},
            {"payment_id": "P4", "sale_id": "S4", "customer_id": "C3", "amount": "40.00", "payment_type": "cash", "payment_timestamp": "2026-01-01T04:00:00", "status": "settled"},
        ]
    }


def test_invalid_state_transition_and_validator_evidence() -> None:
    primitive_result = PRIMITIVE_REGISTRY.execute(
        "invalid_state_transition",
        PrimitiveExecutionContext(dataset=_dataset(), spec=RETAIL_SPEC, parameters={"table": "payments", "id_column": "payment_id", "status_column": "status", "affected_rate_default": 0.50}, seed=31),
    )
    validation = VALIDATOR_REGISTRY.validate(
        "state_transition_validator",
        ValidatorExecutionContext(dataset=primitive_result.dataset, spec=RETAIL_SPEC, parameters={}, primitive_result=primitive_result, expected_count=primitive_result.actual_mutated_count),
    )
    assert validation["status"] == "PASS"
    assert validation["detected_count"] == primitive_result.actual_mutated_count
    assert validation["evidence"]["transitions"][0]["violated_rule"] == "impossible_transition"


def test_stale_timestamp_age_mode_and_boundary() -> None:
    primitive_result = PRIMITIVE_REGISTRY.execute(
        "stale_timestamp",
        PrimitiveExecutionContext(dataset=_dataset(), spec=RETAIL_SPEC, parameters={"table": "payments", "id_column": "payment_id", "timestamp_column": "payment_timestamp", "affected_rate_default": 0.25}, seed=32),
    )
    validation = VALIDATOR_REGISTRY.validate(
        "sla_validator",
        ValidatorExecutionContext(dataset=primitive_result.dataset, spec=RETAIL_SPEC, parameters={}, primitive_result=primitive_result, expected_count=primitive_result.actual_mutated_count),
    )
    assert validation["status"] == "PASS"
    assert validation["evidence"]["violations"][0]["sla_type"] == "age"

    clean_boundary = {
        "payments": [{"payment_id": "P1", "payment_timestamp": "2025-12-31T00:00:00"}],
        "__df_sla_baseline": [{"sla_type": "age", "table": "payments", "pk_column": "payment_id", "pk_value": "P1", "entity_id": "P1", "timestamp_column": "payment_timestamp", "reference_time": "2026-01-01T00:00:00", "allowed_seconds": 86400}],
    }
    boundary = VALIDATOR_REGISTRY.validate("sla_validator", ValidatorExecutionContext(dataset=clean_boundary, spec=RETAIL_SPEC, parameters={}, expected_count=0))
    assert boundary["detected_count"] == 0


def test_timeout_violation_duration_mode() -> None:
    primitive_result = PRIMITIVE_REGISTRY.execute(
        "timeout_violation",
        PrimitiveExecutionContext(dataset=_dataset(), spec=RETAIL_SPEC, parameters={"table": "payments", "id_column": "payment_id", "column": "payment_timestamp", "affected_rate_default": 0.25}, seed=33),
    )
    validation = VALIDATOR_REGISTRY.validate(
        "sla_validator",
        ValidatorExecutionContext(dataset=primitive_result.dataset, spec=RETAIL_SPEC, parameters={}, primitive_result=primitive_result, expected_count=primitive_result.actual_mutated_count),
    )
    assert validation["status"] == "PASS"
    assert validation["evidence"]["violations"][0]["sla_type"] == "duration"
    assert validation["evidence"]["violations"][0]["violation_seconds"] > 0


def test_volume_spike_and_drop_group_level_reconciliation() -> None:
    spike = PRIMITIVE_REGISTRY.execute(
        "volume_spike",
        PrimitiveExecutionContext(dataset=_dataset(), spec=RETAIL_SPEC, parameters={"table": "payments", "id_column": "payment_id", "group_key": "customer_id", "affected_rate_default": 0.50}, seed=34),
    )
    spike_validation = VALIDATOR_REGISTRY.validate(
        "volume_anomaly_validator",
        ValidatorExecutionContext(dataset=spike.dataset, spec=RETAIL_SPEC, parameters={}, primitive_result=spike, expected_count=spike.actual_mutated_count),
    )
    assert spike_validation["status"] == "PASS"
    assert spike_validation["evidence"]["anomalies"][0]["anomaly_type"] == "spike"

    drop = PRIMITIVE_REGISTRY.execute(
        "volume_drop",
        PrimitiveExecutionContext(dataset=_dataset(), spec=RETAIL_SPEC, parameters={"table": "payments", "id_column": "payment_id", "group_key": "customer_id", "affected_rate_default": 0.50}, seed=35),
    )
    drop_validation = VALIDATOR_REGISTRY.validate(
        "volume_anomaly_validator",
        ValidatorExecutionContext(dataset=drop.dataset, spec=RETAIL_SPEC, parameters={}, primitive_result=drop, expected_count=drop.actual_mutated_count),
    )
    assert drop_validation["status"] == "PASS"
    assert drop_validation["evidence"]["anomalies"][0]["anomaly_type"] == "drop"
