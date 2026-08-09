from __future__ import annotations

from datetime import datetime

from dataforge.domains.banking.generators import BankingGenerator
from dataforge.domains.banking.schemas import BANKING_SPEC
from dataforge.domains.logistics.generators import LogisticsGenerator
from dataforge.domains.logistics.schemas import LOGISTICS_SPEC
from dataforge.scenarios.catalog import expanded_scenario_items
from dataforge.scenarios.generic_executor import execute_generic_scenario
from dataforge.scenarios.requirements import REQUIREMENT_RESOLVER
from dataforge.validation import relationship_report, validate


def test_batch_8_banking_card_authorizations_generate_with_valid_lifecycle() -> None:
    data = BankingGenerator(120, seed=811).generate()
    authorizations = data["card_authorizations"]
    assert authorizations
    assert validate(data, BANKING_SPEC)["overall_status"] == "PASS"
    assert relationship_report(data, BANKING_SPEC)["overall_status"] == "PASS"

    for row in authorizations:
        authorized_at = datetime.fromisoformat(row["authorization_timestamp"])
        expires_at = datetime.fromisoformat(row["expires_at"])
        assert expires_at > authorized_at
        assert float(row["authorization_amount"]) > 0
        if row["authorization_status"] == "Captured":
            assert row["captured_at"] != "not_applicable"
            assert row["capture_reference"] != "not_applicable"
        if row["authorization_status"] == "Declined":
            assert row["reason_code"] != "not_applicable"
            assert row["captured_at"] == "not_applicable"


def test_batch_8_logistics_exception_alerts_generate_with_valid_lifecycle() -> None:
    data = LogisticsGenerator(120, seed=812).generate()
    alerts = data["exception_alerts"]
    assert alerts
    assert validate(data, LOGISTICS_SPEC)["overall_status"] == "PASS"
    assert relationship_report(data, LOGISTICS_SPEC)["overall_status"] == "PASS"

    for row in alerts:
        alert_timestamp = datetime.fromisoformat(row["alert_timestamp"])
        assert row["reason_code"]
        assert float(row["estimated_impact_cost"]) >= 0
        if row["status"] == "resolved":
            assert datetime.fromisoformat(row["resolved_at"]) >= alert_timestamp
        else:
            assert row["resolved_at"] == "not_applicable"


def test_batch_8_selected_table_generation_resolves_required_parent_tables() -> None:
    banking = BankingGenerator(50, seed=821)
    banking.selected_tables = {"card_authorizations"}
    banking_data = banking.generate()
    assert {"card_authorizations", "deposit_accounts", "customers", "branches"} <= set(banking_data)
    assert relationship_report(banking_data, BANKING_SPEC)["overall_status"] == "PASS"

    logistics = LogisticsGenerator(50, seed=822)
    logistics.selected_tables = {"exception_alerts"}
    logistics_data = logistics.generate()
    assert {"exception_alerts", "shipments", "customers", "warehouses", "tracking_events"} <= set(logistics_data)
    assert relationship_report(logistics_data, LOGISTICS_SPEC)["overall_status"] == "PASS"


def test_batch_8_promoted_scenarios_execute_end_to_end() -> None:
    new_tables = {"card_authorizations", "exception_alerts"}
    scenarios = [
        item
        for item in expanded_scenario_items()
        if item.execution_status == "executable" and item.primary_table in new_tables
    ]
    assert len(scenarios) == 15
    assert {item.domain for item in scenarios} == {"banking", "logistics"}
    assert all(REQUIREMENT_RESOLVER.resolve(item).execution_supported for item in scenarios)

    first_results = [execute_generic_scenario(scenario, records=80, seed=808) for scenario in scenarios]
    second_results = [execute_generic_scenario(scenario, records=80, seed=808) for scenario in scenarios]
    for first, second in zip(first_results, second_results):
        assert first.scenario_outcome == "PASS", first.scenario_id
        assert first.primitive_result["actual_mutated_count"] > 0, first.scenario_id
        assert first.validator_result["detected_count"] >= first.primitive_result["actual_mutated_count"], first.scenario_id
        assert first.validator_result["reconciliation_status"] == "PASS", first.scenario_id
        assert first.validator_result["evidence"], first.scenario_id
        assert first.primitive_result["affected_entity_ids"] == second.primitive_result["affected_entity_ids"]
