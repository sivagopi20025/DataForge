from __future__ import annotations

import pytest

from dataforge.scenarios.catalog import expanded_scenario_items
from dataforge.scenarios.generic_executor import execute_generic_scenario
from dataforge.scenarios.primitives import PRIMITIVE_REGISTRY
from dataforge.scenarios.requirements import REQUIREMENT_RESOLVER
from dataforge.scenarios.validator_registry import VALIDATOR_REGISTRY


def test_primitive_registry_resolves_legacy_aliases_to_canonical_primitives() -> None:
    assert PRIMITIVE_REGISTRY.resolve_id("duplicate_transaction") == "duplicate_entity"
    assert PRIMITIVE_REGISTRY.resolve_id("temperature_threshold_breach") == "value_above_threshold"
    assert PRIMITIVE_REGISTRY.resolve_id("settlement_delay") == "timestamp_delay"
    with pytest.raises(KeyError):
        PRIMITIVE_REGISTRY.get("unknown_future_primitive")


def test_validator_registry_distinguishes_runtime_and_metadata_only_patterns() -> None:
    assert "duplicate_key_validator" in VALIDATOR_REGISTRY.runtime_implemented()
    assert "sla_validator" in VALIDATOR_REGISTRY.runtime_implemented()
    assert "distribution_validator" in VALIDATOR_REGISTRY.metadata_only()
    with pytest.raises(KeyError):
        VALIDATOR_REGISTRY.get("unknown_future_validator")


def test_requirement_resolver_marks_ready_and_specification_only_scenarios() -> None:
    executable = next(item for item in expanded_scenario_items() if item.execution_status == "executable")
    resolution = REQUIREMENT_RESOLVER.resolve(executable)
    assert resolution.execution_supported is True
    assert resolution.readiness() == "ready_now"

    specification_only = next(item for item in expanded_scenario_items() if item.execution_status == "specification_only")
    blocked = REQUIREMENT_RESOLVER.resolve(specification_only)
    assert blocked.execution_supported is False
    assert blocked.dependencies.has_dependencies
    assert blocked.readiness() == specification_only.implementation_readiness


def test_generic_executor_returns_evidence_and_reconciled_counts() -> None:
    scenario = next(item for item in expanded_scenario_items() if item.scenario_id == "ecommerce_payment_retry")
    result = execute_generic_scenario(scenario, records=100, seed=7)
    assert result.scenario_outcome == "PASS"
    assert result.primitive_result["primitive_id"] == "duplicate_entity"
    assert result.primitive_result["selected_count"] == result.primitive_result["actual_mutated_count"]
    assert result.validator_result["detected_count"] == result.primitive_result["actual_mutated_count"]
    assert result.validator_result["reconciliation_status"] == "PASS"
    assert result.validator_result["evidence"]


def test_generic_executor_is_seed_deterministic_and_seed_variable() -> None:
    scenario = next(item for item in expanded_scenario_items() if item.scenario_id == "ecommerce_payment_retry")
    first = execute_generic_scenario(scenario, records=100, seed=17)
    second = execute_generic_scenario(scenario, records=100, seed=17)
    third = execute_generic_scenario(scenario, records=100, seed=18)
    assert first.primitive_result["affected_entity_ids"] == second.primitive_result["affected_entity_ids"]
    assert first.primitive_result["affected_entity_ids"] != third.primitive_result["affected_entity_ids"]


def test_runtime_capable_subset_is_honest_and_not_forced_to_all_760() -> None:
    items = expanded_scenario_items()
    executable = [item for item in items if item.execution_status == "executable"]
    custom = [item for item in items if item.execution_status == "custom_reference"]
    specification_only = [item for item in items if item.execution_status == "specification_only"]
    assert len(items) == 760
    assert len(executable) == 521
    assert len(executable) + len(custom) == 531
    assert len(custom) == 10
    assert specification_only


def test_all_batch_1_promoted_scenarios_execute_end_to_end() -> None:
    batch_1_primitives = {"timestamp_out_of_order", "sequence_gap", "duplicate_event"}
    scenarios = [
        item
        for item in expanded_scenario_items()
        if item.execution_status == "executable"
        and (item.failure_primitive in batch_1_primitives or item.primitive_parameters.get("legacy_runtime_primitive"))
    ]
    assert len(scenarios) >= 71
    for scenario in scenarios:
        result = execute_generic_scenario(scenario, records=50, seed=101)
        assert result.scenario_outcome == "PASS", scenario.scenario_id
        assert result.primitive_result["actual_mutated_count"] > 0, scenario.scenario_id
        assert result.validator_result["detected_count"] >= result.primitive_result["actual_mutated_count"], scenario.scenario_id
        assert result.validator_result["reconciliation_status"] == "PASS", scenario.scenario_id
        assert result.validator_result["evidence"], scenario.scenario_id


def test_batch_1_sequence_capabilities_reuse_across_domains() -> None:
    sequence_scenarios = [
        item
        for item in expanded_scenario_items()
        if item.execution_status == "executable" and item.validator_pattern == "sequence_validator"
    ]
    assert {item.failure_primitive for item in sequence_scenarios} >= {"timestamp_out_of_order", "sequence_gap", "duplicate_event"}
    assert len({item.domain for item in sequence_scenarios}) >= 8


def test_batch_2_reconciliation_capabilities_are_registered() -> None:
    assert {"cross_table_mismatch", "aggregate_mismatch"} <= PRIMITIVE_REGISTRY.runtime_implemented()
    assert {"cross_table_consistency_validator", "aggregate_balance_validator"} <= VALIDATOR_REGISTRY.runtime_implemented()


def test_all_batch_2_promoted_scenarios_execute_end_to_end() -> None:
    scenarios = [
        item
        for item in expanded_scenario_items()
        if item.execution_status == "executable" and item.failure_primitive == "cross_table_mismatch"
    ]
    assert len(scenarios) == 49
    assert len({item.domain for item in scenarios}) >= 8
    for scenario in scenarios:
        result = execute_generic_scenario(scenario, records=80, seed=207)
        assert result.scenario_outcome == "PASS", scenario.scenario_id
        assert result.primitive_result["actual_mutated_count"] > 0, scenario.scenario_id
        assert result.validator_result["detected_count"] >= result.primitive_result["actual_mutated_count"], scenario.scenario_id
        assert result.validator_result["reconciliation_status"] == "PASS", scenario.scenario_id
        comparisons = result.validator_result["evidence"].get("comparisons", [])
        assert comparisons, scenario.scenario_id
        assert {"expected_value", "actual_value", "difference", "comparison_rule"} <= set(comparisons[0]), scenario.scenario_id


def test_batch_3_state_sla_and_volume_capabilities_are_registered() -> None:
    assert {"invalid_state_transition", "stale_timestamp", "timeout_violation", "volume_spike", "volume_drop"} <= PRIMITIVE_REGISTRY.runtime_implemented()
    assert {"state_transition_validator", "sla_validator", "volume_anomaly_validator"} <= VALIDATOR_REGISTRY.runtime_implemented()


def test_all_batch_3_promoted_scenarios_execute_end_to_end() -> None:
    batch_3_primitives = {"invalid_state_transition", "stale_timestamp", "timeout_violation", "volume_spike", "volume_drop", "timestamp_delay"}
    scenarios = [
        item
        for item in expanded_scenario_items()
        if item.execution_status == "executable" and item.failure_primitive in batch_3_primitives and item.validator_pattern in {"state_transition_validator", "sla_validator", "volume_anomaly_validator"}
    ]
    assert len(scenarios) == 147
    assert len({item.domain for item in scenarios}) == 10
    for scenario in scenarios:
        result = execute_generic_scenario(scenario, records=80, seed=307)
        assert result.scenario_outcome == "PASS", scenario.scenario_id
        assert result.primitive_result["actual_mutated_count"] > 0, scenario.scenario_id
        assert result.validator_result["detected_count"] >= result.primitive_result["actual_mutated_count"], scenario.scenario_id
        assert result.validator_result["reconciliation_status"] == "PASS", scenario.scenario_id
        assert result.validator_result["evidence"], scenario.scenario_id


def test_batch_4_capabilities_are_registered() -> None:
    assert {"retry_burst", "value_below_threshold", "availability_failure", "policy_violation", "geographic_jump"} <= PRIMITIVE_REGISTRY.runtime_implemented()
    assert {"policy_validator", "availability_validator", "geographic_validator", "retry_pattern_validator"} <= VALIDATOR_REGISTRY.runtime_implemented()


def test_all_batch_4_promoted_scenarios_execute_end_to_end() -> None:
    batch_4_primitives = {"value_below_threshold", "availability_failure", "policy_violation", "geographic_jump", "negative_numeric_value"}
    scenarios = [
        item
        for item in expanded_scenario_items()
        if item.execution_status == "executable" and item.failure_primitive in batch_4_primitives and item.validator_pattern in {"threshold_validator", "policy_validator", "availability_validator", "geographic_validator"}
    ]
    assert len(scenarios) == 46
    assert len({item.domain for item in scenarios}) >= 9
    for scenario in scenarios:
        result = execute_generic_scenario(scenario, records=80, seed=407)
        assert result.scenario_outcome == "PASS", scenario.scenario_id
        assert result.primitive_result["actual_mutated_count"] > 0, scenario.scenario_id
        assert result.validator_result["detected_count"] >= result.primitive_result["actual_mutated_count"], scenario.scenario_id
        assert result.validator_result["reconciliation_status"] == "PASS", scenario.scenario_id
        assert result.validator_result["evidence"], scenario.scenario_id
