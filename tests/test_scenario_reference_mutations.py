from __future__ import annotations

from dataforge.domains import DOMAIN_GENERATORS, DOMAIN_SPECS
from dataforge.scenarios.executor import failure_rates_for_config, resolve_scenario_run
from dataforge.scenarios.models import ScenarioRunConfig
from dataforge.scenarios.mutations import apply_reference_scenario_mutations
from dataforge.scenarios.validators import scenario_outcome_from_validations, validate_scenario_dataset
from dataforge.validation import validate


REFERENCE_SCENARIOS = [
    ("retail_payment_retry", "payments", "duplicate_business_payment"),
    ("banking_duplicate_transfer", "transfers", "duplicate_transfer"),
    ("healthcare_ghost_provider", "claims", "ghost_provider"),
    ("manufacturing_defect_spike", "quality_checks", "defect_spike"),
    ("telecom_tower_congestion", "data_sessions", "tower_congestion"),
    ("logistics_cold_chain_failure", "delivery_records", "temperature_breach"),
    ("finance_settlement_delay", "transactions", "settlement_delay"),
    ("insurance_coverage_exceeded", "claims", "coverage_exceeded"),
    ("education_grade_calculation_error", "enrollments", "grade_calculation_error"),
    ("ecommerce_inventory_oversell", "product_listings", "inventory_oversell"),
]


def test_reference_scenario_mutations_are_deterministic_and_controlled() -> None:
    for scenario_id, table, expected_failure in REFERENCE_SCENARIOS:
        scenario, config = resolve_scenario_run(ScenarioRunConfig(scenario_id=scenario_id, records=500, severity="medium"))
        spec = DOMAIN_SPECS[scenario.domain]
        clean = DOMAIN_GENERATORS[scenario.domain](500, seed=42).generate()
        rates = failure_rates_for_config(scenario, config)
        first, first_events, first_report = apply_reference_scenario_mutations(clean, scenario=scenario, config=config, spec=spec, seed=42, rates=rates)
        second, second_events, second_report = apply_reference_scenario_mutations(clean, scenario=scenario, config=config, spec=spec, seed=42, rates=rates)

        assert first == second
        assert [event.__dict__ for event in first_events] == [event.__dict__ for event in second_events]
        assert expected_failure in {event.failure_type for event in first_events}
        assert first_report["scenario_outcome"] == "PASS"
        assert first_report["actual_mutation_counts"][expected_failure] >= 1
        assert len(first[table]) >= len(clean[table])


def test_reference_scenario_mutations_make_validation_fail_as_expected() -> None:
    for scenario_id, _, _ in REFERENCE_SCENARIOS:
        scenario, config = resolve_scenario_run(ScenarioRunConfig(scenario_id=scenario_id, records=300, severity="medium"))
        spec = DOMAIN_SPECS[scenario.domain]
        clean = DOMAIN_GENERATORS[scenario.domain](300, seed=43).generate()
        assert validate(clean, spec)["quality_score"] == 100
        mutated, events, report = apply_reference_scenario_mutations(clean, scenario=scenario, config=config, spec=spec, seed=43, rates=failure_rates_for_config(scenario, config))
        validation = validate(mutated, spec)
        assert events
        assert report["scenario_outcome"] == "PASS"
        assert validation["quality_score"] < 100


def test_reference_scenario_validators_return_evidence_and_reconcile() -> None:
    for scenario_id, _, _ in REFERENCE_SCENARIOS:
        scenario, config = resolve_scenario_run(ScenarioRunConfig(scenario_id=scenario_id, records=300, severity="medium"))
        spec = DOMAIN_SPECS[scenario.domain]
        clean = DOMAIN_GENERATORS[scenario.domain](300, seed=51).generate()
        mutated, events, report = apply_reference_scenario_mutations(clean, scenario=scenario, config=config, spec=spec, seed=51, rates=failure_rates_for_config(scenario, config))
        validations = validate_scenario_dataset(mutated, scenario=scenario, config=config, expected_counts=report["actual_mutation_counts"])

        assert events
        assert validations
        assert scenario_outcome_from_validations(validations) == "PASS"
        for validation in validations:
            assert validation["validation_id"]
            assert validation["scenario_id"] == scenario_id
            assert validation["status"] == "PASS"
            assert validation["expected_count"] >= 0
            assert validation["detected_count"] >= validation["expected_count"]
            assert validation["evidence"]
            assert validation["reconciliation_status"] == "PASS"


def test_reference_scenario_validators_show_seed_variation() -> None:
    for scenario_id, _, expected_failure in REFERENCE_SCENARIOS:
        scenario, config = resolve_scenario_run(ScenarioRunConfig(scenario_id=scenario_id, records=400, severity="medium"))
        spec = DOMAIN_SPECS[scenario.domain]
        rates = failure_rates_for_config(scenario, config)
        clean_a = DOMAIN_GENERATORS[scenario.domain](400, seed=101).generate()
        clean_b = DOMAIN_GENERATORS[scenario.domain](400, seed=202).generate()
        _, _, report_a = apply_reference_scenario_mutations(clean_a, scenario=scenario, config=config, spec=spec, seed=101, rates=rates)
        _, _, report_b = apply_reference_scenario_mutations(clean_b, scenario=scenario, config=config, spec=spec, seed=202, rates=rates)

        assert report_a["actual_mutation_counts"][expected_failure] == report_b["actual_mutation_counts"][expected_failure]
        assert report_a["reconciliation_by_failure"][expected_failure]["status"] == "PASS"
        assert report_b["reconciliation_by_failure"][expected_failure]["status"] == "PASS"
