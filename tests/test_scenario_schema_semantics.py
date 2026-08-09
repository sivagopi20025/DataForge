from __future__ import annotations

import yaml

from dataforge.scenarios.catalog import expanded_scenario_items, load_domain_column_semantics
from dataforge.scenarios.generic_executor import execute_generic_scenario
from dataforge.scenarios.schema_semantics import COLUMN_SEMANTIC_RESOLVER


def test_domain_column_semantic_catalog_covers_every_domain_table_and_column() -> None:
    catalog = load_domain_column_semantics()
    assert catalog["version"] == "1.4.0"
    assert "retail" in catalog["domains"]
    for domain, tables in catalog["domains"].items():
        assert tables, domain
        for table, columns in tables.items():
            assert columns, f"{domain}.{table}"
            for column in columns:
                assert column["domain"] == domain
                assert column["table"] == table
                assert column["column"]
                assert column["semantic_role"]
                assert column["data_type"]
                assert "aliases" in column


def test_amount_timestamp_status_and_group_key_resolution_use_domain_native_columns() -> None:
    assert COLUMN_SEMANTIC_RESOLVER.resolve("healthcare", "claims", "amount").resolved_column == "claim_amount"
    assert COLUMN_SEMANTIC_RESOLVER.resolve("banking", "transfers", "amount").resolved_column == "transfer_amount"
    assert COLUMN_SEMANTIC_RESOLVER.resolve("ecommerce", "orders", "actual_amount").resolved_column == "total_amount"
    assert COLUMN_SEMANTIC_RESOLVER.resolve("finance", "transactions", "event_timestamp").resolved_column == "transaction_timestamp"
    assert COLUMN_SEMANTIC_RESOLVER.resolve("insurance", "claims", "scenario_status_code").resolved_column == "claim_status"
    assert COLUMN_SEMANTIC_RESOLVER.resolve("retail", "sales", "reconciliation_group_id").resolved_column in {"store_id", "customer_id", "employee_id", "promotion_id"}


def test_reason_code_and_idempotency_key_are_not_falsely_mapped() -> None:
    assert COLUMN_SEMANTIC_RESOLVER.resolve("banking", "branches", "reason_code").resolved is False
    assert COLUMN_SEMANTIC_RESOLVER.resolve("retail", "payments", "idempotency_key").resolved is False


def test_id_column_normalization_never_uses_amount_columns_as_identifiers() -> None:
    normalized = COLUMN_SEMANTIC_RESOLVER.normalize_parameters(
        "ecommerce",
        "shipments",
        {"table": "shipments", "id_column": "actual_amount", "columns": ["actual_amount", "expected_amount"]},
    )
    assert normalized["id_column"] == "shipment_id"
    assert normalized["columns"] == ["shipping_cost"]


def test_batch_5_metadata_only_promotions_execute_with_resolved_columns() -> None:
    scenarios = [
        item
        for item in expanded_scenario_items()
        if item.execution_status == "executable"
        and item.scenario_id
        in {
            "healthcare_reconciliation_claim_aggregate_mismatch_04",
            "banking_payments_payment_calculation_error_03",
            "ecommerce_reconciliation_order_cross_table_mismatch_02",
            "retail_returns_return_timestamp_delay_04",
        }
    ]
    assert len(scenarios) == 4
    for scenario in scenarios:
        result = execute_generic_scenario(scenario, records=80, seed=805)
        assert result.scenario_outcome == "PASS", scenario.scenario_id
        assert result.primitive_result["actual_mutated_count"] > 0
        assert result.validator_result["reconciliation_status"] == "PASS"


def test_schema_leverage_report_documents_batch_9_manufacturing_depth_unlocks() -> None:
    report = yaml.safe_load(open("dataforge/scenarios/catalog/schema_leverage_report.yaml", encoding="utf-8"))
    assert report["executable_scenarios_gained_by_physical_schema_changes"] == 9
    assert report["tables_added_this_batch"] == []
    assert report["newly_executable_by_domain"] == {"manufacturing": 9}
    assert "manufacturing.work_orders.idempotency_key" in report["columns_implemented_this_batch"]


def test_batch_6_finance_schema_depth_promotions_execute_end_to_end() -> None:
    scenario_ids = {
        "finance_risk_trade_negative_numeric_value_01",
        "finance_market_data_market_data_cross_table_mismatch_04",
        "finance_reconciliation_position_aggregate_mismatch_01",
        "finance_trading_risk_event_stale_timestamp_02",
    }
    scenarios = [item for item in expanded_scenario_items() if item.scenario_id in scenario_ids]
    assert len(scenarios) == len(scenario_ids)
    assert all(item.execution_status == "executable" for item in scenarios)
    for scenario in scenarios:
        result = execute_generic_scenario(scenario, records=80, seed=906)
        assert result.scenario_outcome == "PASS", scenario.scenario_id
        assert result.primitive_result["actual_mutated_count"] > 0
        assert result.validator_result["reconciliation_status"] == "PASS"
