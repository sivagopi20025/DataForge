from __future__ import annotations

from dataforge.scenarios import all_scenarios, find_scenarios, validate_catalog
from dataforge.scenarios.executor import build_generation_payload, failure_rates_for_config, resolve_scenario_run
from dataforge.scenarios.matcher import match_scenarios
from dataforge.scenarios.models import ScenarioRunConfig
from dataforge.scenarios.validator import resolve_config


REFERENCE_SCENARIOS = [
    "retail_payment_retry",
    "banking_duplicate_transfer",
    "healthcare_ghost_provider",
    "manufacturing_defect_spike",
    "telecom_tower_congestion",
]


def test_all_50_scenario_definitions_validate() -> None:
    scenarios = all_scenarios()
    assert len(scenarios) == 50
    assert len({scenario.scenario_id for scenario in scenarios}) == 50
    assert validate_catalog() == []
    assert {scenario.domain for scenario in scenarios} == {
        "retail",
        "logistics",
        "healthcare",
        "finance",
        "insurance",
        "banking",
        "manufacturing",
        "telecommunications",
        "education",
        "ecommerce",
    }


def test_scenario_search_by_domain_tag_alias_mode_and_keyword() -> None:
    assert len(find_scenarios(domain="banking")) == 5
    assert find_scenarios(tag="duplicate")
    assert find_scenarios(mode="streaming")
    assert find_scenarios(keyword="ghost provider")[0].scenario_id == "healthcare_ghost_provider"
    assert match_scenarios("duplicate transfer timeout")[0]["scenario_id"] == "banking_duplicate_transfer"


def test_scenario_config_defaults_and_validation_rules() -> None:
    result = resolve_config(ScenarioRunConfig(scenario_id="banking_duplicate_transfer"))
    assert result.status == "PASS"
    assert result.resolved_config is not None
    assert result.resolved_config.domain == "banking"
    assert result.resolved_config.records == 10_000
    assert result.resolved_config.severity == "medium"

    invalid = resolve_config(ScenarioRunConfig(scenario_id="banking_duplicate_transfer", mode="batch", event_rate=100))
    assert invalid.status == "FAIL"
    assert "only valid for streaming" in invalid.errors[0]

    zero = resolve_config(ScenarioRunConfig(scenario_id="retail_payment_retry", records=0))
    assert zero.status == "FAIL"
    assert "records must be at least" in zero.errors[0]


def test_reference_scenarios_build_generation_payloads() -> None:
    for scenario_id in REFERENCE_SCENARIOS:
        payload = build_generation_payload(ScenarioRunConfig(scenario_id=scenario_id, records=500, output_format="csv"))
        assert payload["scenario_id"] == scenario_id
        assert payload["records"] == 500
        assert payload["issues"]
        assert payload["scenario_definition"]["scenario_id"] == scenario_id
        assert payload["scenario_run_config"]["scenario_id"] == scenario_id
        assert payload["expected_validations"]["expected_validations"]


def test_severity_and_override_rates_are_controlled() -> None:
    scenario, config = resolve_scenario_run(ScenarioRunConfig(scenario_id="retail_payment_retry", severity="high"))
    assert failure_rates_for_config(scenario, config)["duplicate_records"] == 0.05

    scenario, config = resolve_scenario_run(
        ScenarioRunConfig(
            scenario_id="retail_payment_retry",
            failure_overrides={"retail_payment_retry_failure": {"rate": 0.02}},
        )
    )
    assert failure_rates_for_config(scenario, config)["duplicate_records"] == 0.02

