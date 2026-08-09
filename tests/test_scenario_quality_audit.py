from __future__ import annotations

import yaml

from dataforge.domains.manufacturing.generators import ManufacturingGenerator
from dataforge.domains.manufacturing.schemas import MANUFACTURING_SPEC
from dataforge.scenarios.catalog import expanded_scenario_items
from dataforge.scenarios.generic_executor import execute_generic_scenario
from dataforge.scenarios.quality import build_scenario_quality_summary, validator_independence_class
from dataforge.validation import relationship_report, validate


BATCH_9_SCENARIOS = {
    "manufacturing_capacity_production_line_retry_burst_06",
    "manufacturing_downtime_work_order_retry_burst_06",
    "manufacturing_inventory_work_order_inventory_oversell_06",
    "manufacturing_quality_quality_check_missing_child_record_03",
    "manufacturing_reconciliation_factorie_aggregate_mismatch_01",
    "manufacturing_suppliers_quality_check_calculation_error_01",
    "manufacturing_suppliers_quality_check_duplicate_retry_06",
    "manufacturing_suppliers_quality_check_retry_burst_05",
    "manufacturing_work_orders_factorie_duplicate_retry_04",
}


def test_quality_audit_covers_every_runtime_capable_scenario() -> None:
    audit = yaml.safe_load(open("dataforge/scenarios/catalog/scenario_quality_audit.yaml", encoding="utf-8"))
    runtime = [item for item in expanded_scenario_items() if item.execution_status in {"executable", "custom_reference"}]
    assert audit["total_runtime_capable"] == len(runtime) == 531
    assert len(audit["scenarios"]) == len(runtime)
    assert audit["v1_ready"] == 531
    assert audit["needs_fix"] == 0
    assert set(audit["validator_independence_counts"]) <= {
        "strong_independent",
        "partially_independent",
        "metadata_assisted",
        "weak",
    }
    assert audit["validator_independence_counts"]["strong_independent"] > audit["validator_independence_counts"]["partially_independent"]


def test_quality_summary_matches_audit_artifact() -> None:
    audit = yaml.safe_load(open("dataforge/scenarios/catalog/scenario_quality_audit.yaml", encoding="utf-8"))
    summary = build_scenario_quality_summary(audit)
    assert summary["total_runtime_capable"] == 531
    assert summary["v1_ready"] == 531
    assert summary["needs_fix"] == 0
    assert summary["v1_quality_gate"]["requires_seed_determinism"] is True


def test_validator_independence_classifier_is_stable() -> None:
    assert validator_independence_class("aggregate_balance_validator") == "strong_independent"
    assert validator_independence_class("calculation_validator") == "partially_independent"
    assert validator_independence_class("distribution_validator") == "weak"


def test_batch_9_manufacturing_columns_are_generated_cleanly() -> None:
    data = ManufacturingGenerator(100, seed=920).generate()
    assert data["work_orders"][0]["idempotency_key"].startswith("MFG-WO-")
    assert "risk_score" in data["work_orders"][0]
    assert "planned_capacity_amount" in data["factories"][0]
    assert data["quality_checks"][0]["scenario_status_code"] == data["quality_checks"][0]["result"]
    assert validate(data, MANUFACTURING_SPEC)["overall_status"] == "PASS"
    assert relationship_report(data, MANUFACTURING_SPEC)["overall_status"] == "PASS"


def test_batch_9_promoted_manufacturing_scenarios_execute_end_to_end() -> None:
    scenarios = [item for item in expanded_scenario_items() if item.scenario_id in BATCH_9_SCENARIOS]
    assert len(scenarios) == 9
    assert all(item.execution_status == "executable" for item in scenarios)
    first = [execute_generic_scenario(scenario, records=90, seed=909) for scenario in scenarios]
    second = [execute_generic_scenario(scenario, records=90, seed=909) for scenario in scenarios]
    for left, right in zip(first, second):
        assert left.scenario_outcome == "PASS", left.scenario_id
        assert left.primitive_result["actual_mutated_count"] > 0
        assert left.validator_result["reconciliation_status"] == "PASS"
        assert left.validator_result["detected_count"] >= left.primitive_result["actual_mutated_count"]
        assert left.validator_result["evidence"]
        assert left.primitive_result["affected_entity_ids"] == right.primitive_result["affected_entity_ids"]
