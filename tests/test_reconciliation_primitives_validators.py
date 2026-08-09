from __future__ import annotations

from dataforge.domains.retail.schemas import RETAIL_SPEC
from dataforge.scenarios.primitives import PRIMITIVE_REGISTRY, PrimitiveExecutionContext
from dataforge.scenarios.validator_registry import VALIDATOR_REGISTRY, ValidatorExecutionContext


def _retail_dataset() -> dict[str, list[dict]]:
    return {
        "sales": [
            {"sale_id": "S1", "store_id": "ST1", "customer_id": "C1", "product_id": "P1", "promotion_id": "", "quantity": 1, "unit_price": "10.00", "sale_amount": "10.00", "sale_timestamp": "2026-01-01T10:00:00", "payment_method": "card"},
            {"sale_id": "S2", "store_id": "ST1", "customer_id": "C2", "product_id": "P2", "promotion_id": "", "quantity": 2, "unit_price": "20.00", "sale_amount": "40.00", "sale_timestamp": "2026-01-01T11:00:00", "payment_method": "card"},
            {"sale_id": "S3", "store_id": "ST2", "customer_id": "C3", "product_id": "P3", "promotion_id": "", "quantity": 1, "unit_price": "30.00", "sale_amount": "30.00", "sale_timestamp": "2026-01-01T12:00:00", "payment_method": "cash"},
        ]
    }


def test_cross_table_mismatch_evidence_and_decimal_tolerance() -> None:
    dataset = _retail_dataset()
    primitive_result = PRIMITIVE_REGISTRY.execute(
        "cross_table_mismatch",
        PrimitiveExecutionContext(
            dataset=dataset,
            spec=RETAIL_SPEC,
            parameters={"table": "sales", "id_column": "sale_id", "column": "sale_amount", "affected_rate_default": 0.34},
            seed=11,
        ),
    )
    validation = VALIDATOR_REGISTRY.validate(
        "cross_table_consistency_validator",
        ValidatorExecutionContext(
            dataset=primitive_result.dataset,
            spec=RETAIL_SPEC,
            parameters={"tolerance": "0.01"},
            primitive_result=primitive_result,
            expected_count=primitive_result.actual_mutated_count,
        ),
    )
    assert validation["status"] == "PASS"
    assert validation["detected_count"] == primitive_result.actual_mutated_count
    comparison = validation["evidence"]["comparisons"][0]
    assert comparison["source_table"] == "sales"
    assert comparison["difference"] != "0"


def test_cross_table_validator_honors_tolerance() -> None:
    dataset = {
        "sales": [
            {"sale_id": "S1", "sale_amount": "10.005"},
        ],
        "__df_cross_table_baseline": [
            {"source_table": "sales", "source_pk_column": "sale_id", "source_pk_value": "S1", "source_entity_id": "S1", "source_column": "sale_amount", "expected_value": "10.00"},
        ],
    }
    validation = VALIDATOR_REGISTRY.validate(
        "cross_table_consistency_validator",
        ValidatorExecutionContext(dataset=dataset, spec=RETAIL_SPEC, parameters={"tolerance": "0.01"}, expected_count=0),
    )
    assert validation["status"] == "PASS"
    assert validation["detected_count"] == 0


def test_aggregate_mismatch_group_level_reconciliation() -> None:
    dataset = _retail_dataset()
    primitive_result = PRIMITIVE_REGISTRY.execute(
        "aggregate_mismatch",
        PrimitiveExecutionContext(
            dataset=dataset,
            spec=RETAIL_SPEC,
            parameters={"table": "sales", "id_column": "sale_id", "group_key": "store_id", "column": "sale_amount", "affected_rate_default": 0.50},
            seed=19,
        ),
    )
    validation = VALIDATOR_REGISTRY.validate(
        "aggregate_balance_validator",
        ValidatorExecutionContext(
            dataset=primitive_result.dataset,
            spec=RETAIL_SPEC,
            parameters={"tolerance": "0.01"},
            primitive_result=primitive_result,
            expected_count=primitive_result.actual_mutated_count,
        ),
    )
    assert validation["status"] == "PASS"
    assert validation["selected_count"] == primitive_result.selected_count
    assert validation["actual_mutated_count"] == primitive_result.actual_mutated_count
    assert validation["detected_count"] == primitive_result.actual_mutated_count
    group = validation["evidence"]["groups"][0]
    assert {"group_id", "expected_aggregate", "actual_aggregate", "difference", "tolerance"} <= set(group)


def test_aggregate_mismatch_fails_cleanly_for_missing_group_key() -> None:
    dataset = _retail_dataset()
    try:
        PRIMITIVE_REGISTRY.execute(
            "aggregate_mismatch",
            PrimitiveExecutionContext(dataset=dataset, spec=RETAIL_SPEC, parameters={"table": "sales", "group_key": "missing_group"}, seed=1),
        )
    except ValueError as exc:
        assert "group column is missing" in str(exc)
    else:
        raise AssertionError("aggregate_mismatch should reject missing group keys")
