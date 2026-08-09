from __future__ import annotations

import pytest
import yaml
from pydantic import ValidationError

from dataforge.scenarios.catalog import expanded_scenario_items
from dataforge.scenarios.configuration import (
    FailurePlan,
    FailurePlanItem,
    compatible_primitives_for_scenario,
    ground_truth_from_execution_result,
    scenario_configuration_metadata,
    validate_failure_plan,
)
from dataforge.scenarios.generic_executor import execute_generic_scenario


def _scenario():
    return next(item for item in expanded_scenario_items() if item.scenario_id == "ecommerce_payment_retry")


def test_failure_plan_yaml_contract_documents_safe_controls() -> None:
    contract = yaml.safe_load(open("dataforge/scenarios/catalog/failure_plan_contract.yaml", encoding="utf-8"))
    assert contract["fields"]["overlap_mode"] == ["non_overlapping", "allow_overlap"]
    assert "primitive must be runtime implemented" in " ".join(contract["validation_rules"])


def test_failure_plan_validates_rates_counts_and_compatible_primitives() -> None:
    scenario = _scenario()
    plan = FailurePlan(
        scenario_id=scenario.scenario_id,
        failures=[FailurePlanItem(primitive=scenario.failure_primitive, mode="percentage", value=0.03)],
    )
    result = validate_failure_plan(scenario, plan)
    assert result["valid"] is True
    assert scenario.failure_primitive in result["compatible_primitives"]

    invalid = FailurePlan(
        scenario_id=scenario.scenario_id,
        failures=[FailurePlanItem(primitive="value_below_threshold", mode="exact_count", value=1)],
    )
    assert validate_failure_plan(scenario, invalid)["valid"] is False

    with pytest.raises(ValidationError):
        FailurePlan(scenario_id=scenario.scenario_id, failures=[FailurePlanItem(primitive=scenario.failure_primitive, mode="percentage", value=2)])


def test_scenario_configuration_metadata_is_derived_from_catalog() -> None:
    scenario = _scenario()
    metadata = scenario_configuration_metadata(scenario)
    assert metadata["scenario_id"] == scenario.scenario_id
    assert metadata["default_primitive"] == scenario.failure_primitive
    assert scenario.failure_primitive in compatible_primitives_for_scenario(scenario)
    assert metadata["configurable_fields"]["records"]["minimum"] == 0


def test_ground_truth_contract_is_built_from_actual_execution_result() -> None:
    scenario = _scenario()
    result = execute_generic_scenario(scenario, records=100, seed=919)
    ground_truth = ground_truth_from_execution_result(result)
    assert ground_truth.scenario_id == scenario.scenario_id
    assert ground_truth.primitive == result.primitive_result["primitive_id"]
    assert ground_truth.selected_count == result.primitive_result["selected_count"]
    assert ground_truth.actual_mutated_count == result.primitive_result["actual_mutated_count"]
    assert ground_truth.reconciliation_status == "PASS"
