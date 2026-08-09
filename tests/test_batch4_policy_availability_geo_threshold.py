from __future__ import annotations

from dataforge.domains.retail.schemas import RETAIL_SPEC
from dataforge.scenarios.primitives import PRIMITIVE_REGISTRY, PrimitiveExecutionContext
from dataforge.scenarios.validator_registry import VALIDATOR_REGISTRY, ValidatorExecutionContext


def _dataset() -> dict[str, list[dict]]:
    return {
        "payments": [
            {"payment_id": "P1", "sale_id": "S1", "customer_id": "C1", "amount": "10.00", "payment_type": "card", "payment_timestamp": "2026-01-01T01:00:00", "status": "available"},
            {"payment_id": "P2", "sale_id": "S2", "customer_id": "C2", "amount": "20.00", "payment_type": "card", "payment_timestamp": "2026-01-01T02:00:00", "status": "available"},
            {"payment_id": "P3", "sale_id": "S3", "customer_id": "C3", "amount": "30.00", "payment_type": "cash", "payment_timestamp": "2026-01-01T03:00:00", "status": "available"},
        ],
        "stores": [
            {"store_id": "ST1", "store_name": "A", "city": "Austin", "state": "TX", "country": "USA", "open_date": "2020-01-01"},
            {"store_id": "ST2", "store_name": "B", "city": "Boston", "state": "MA", "country": "USA", "open_date": "2020-01-01"},
        ],
    }


def test_value_below_threshold_extends_threshold_validator() -> None:
    primitive = PRIMITIVE_REGISTRY.execute("value_below_threshold", PrimitiveExecutionContext(dataset=_dataset(), spec=RETAIL_SPEC, parameters={"table": "payments", "id_column": "payment_id", "column": "amount", "threshold": "0", "affected_rate_default": 0.34}, seed=41))
    validation = VALIDATOR_REGISTRY.validate("threshold_validator", ValidatorExecutionContext(dataset=primitive.dataset, spec=RETAIL_SPEC, parameters={}, primitive_result=primitive, expected_count=primitive.actual_mutated_count))
    assert validation["status"] == "PASS"
    assert validation["evidence"]["operator"] == "lt"
    assert validation["evidence"]["violations"][0]["observed_value"].startswith("-")


def test_retry_burst_and_retry_pattern_validator() -> None:
    primitive = PRIMITIVE_REGISTRY.execute("retry_burst", PrimitiveExecutionContext(dataset=_dataset(), spec=RETAIL_SPEC, parameters={"table": "payments", "id_column": "payment_id", "affected_rate_default": 0.34, "retry_count": 3}, seed=42))
    validation = VALIDATOR_REGISTRY.validate("retry_pattern_validator", ValidatorExecutionContext(dataset=primitive.dataset, spec=RETAIL_SPEC, parameters={}, primitive_result=primitive, expected_count=primitive.actual_mutated_count))
    assert validation["status"] == "PASS"
    assert primitive.mutation_metadata["rows_created"] >= 3
    assert validation["evidence"]["retries"][0]["attempt_count"] > validation["evidence"]["retries"][0]["allowed_attempts"]


def test_policy_violation_and_validator() -> None:
    primitive = PRIMITIVE_REGISTRY.execute("policy_violation", PrimitiveExecutionContext(dataset=_dataset(), spec=RETAIL_SPEC, parameters={"table": "payments", "id_column": "payment_id", "column": "amount", "affected_rate_default": 0.34}, seed=43))
    validation = VALIDATOR_REGISTRY.validate("policy_validator", ValidatorExecutionContext(dataset=primitive.dataset, spec=RETAIL_SPEC, parameters={}, primitive_result=primitive, expected_count=primitive.actual_mutated_count))
    assert validation["status"] == "PASS"
    assert validation["evidence"]["violations"][0]["violation_reason"] == "upper_bound_exceeded"


def test_availability_failure_and_validator() -> None:
    primitive = PRIMITIVE_REGISTRY.execute("availability_failure", PrimitiveExecutionContext(dataset=_dataset(), spec=RETAIL_SPEC, parameters={"table": "payments", "id_column": "payment_id", "status_column": "status", "affected_rate_default": 0.34}, seed=44))
    validation = VALIDATOR_REGISTRY.validate("availability_validator", ValidatorExecutionContext(dataset=primitive.dataset, spec=RETAIL_SPEC, parameters={}, primitive_result=primitive, expected_count=primitive.actual_mutated_count))
    assert validation["status"] == "PASS"
    assert validation["evidence"]["failures"][0]["violated_rule"] == "unavailable_status"


def test_geographic_jump_and_validator() -> None:
    primitive = PRIMITIVE_REGISTRY.execute("geographic_jump", PrimitiveExecutionContext(dataset=_dataset(), spec=RETAIL_SPEC, parameters={"table": "stores", "id_column": "store_id", "location_column": "city", "affected_rate_default": 0.50}, seed=45))
    validation = VALIDATOR_REGISTRY.validate("geographic_validator", ValidatorExecutionContext(dataset=primitive.dataset, spec=RETAIL_SPEC, parameters={}, primitive_result=primitive, expected_count=primitive.actual_mutated_count))
    assert validation["status"] == "PASS"
    assert validation["evidence"]["jumps"][0]["violated_rule"] == "impossible_zone_transition"
