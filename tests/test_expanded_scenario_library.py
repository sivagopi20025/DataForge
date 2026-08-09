from __future__ import annotations

import yaml

from dataforge.domains import DOMAIN_SPECS
from dataforge.scenarios import all_scenarios
from dataforge.scenarios.catalog import (
    expanded_scenario_items,
    load_domain_table_catalog,
    load_expanded_scenario_library,
    load_failure_taxonomy,
    load_mutation_primitive_plan,
    load_rejected_scenario_library,
    load_scenario_table_coverage,
    load_scenario_taxonomy,
    load_validator_pattern_plan,
    validate_expanded_scenario_library,
    validate_scenario_catalogs,
)


def test_expanded_scenario_library_has_target_size_unique_ids_and_valid_domains() -> None:
    items = expanded_scenario_items()
    assert len(items) == 760
    assert 700 <= len(items) <= 800
    assert len({item.scenario_id for item in items}) == len(items)
    assert {item.domain for item in items} == set(DOMAIN_SPECS)
    assert validate_expanded_scenario_library() == []
    assert validate_scenario_catalogs() == []


def test_existing_50_scenarios_remain_present_and_backward_compatible() -> None:
    expanded_ids = {item.scenario_id for item in expanded_scenario_items()}
    runtime_ids = {scenario.scenario_id for scenario in all_scenarios()}
    assert len(runtime_ids) == 50
    assert runtime_ids <= expanded_ids
    assert sum(1 for item in expanded_scenario_items() if item.status == "reference_implemented") == 10


def test_business_processes_failure_categories_primitives_and_validators_are_known() -> None:
    taxonomy = load_scenario_taxonomy()
    domain_processes = taxonomy["domain_business_processes"]
    categories = set(taxonomy["failure_categories"])
    primitives = {item["primitive_id"] for item in load_failure_taxonomy()["primitive_catalog"]}
    validators = {item["validator_pattern_id"] for item in load_validator_pattern_plan()["validator_patterns"]}

    for item in expanded_scenario_items():
        assert item.business_process in domain_processes[item.domain]
        assert item.failure_category in categories
        assert item.failure_primitive in primitives
        assert item.validator_pattern in validators
        assert item.primitive_parameters
        assert item.validator_parameters


def test_scores_tiers_and_readiness_are_consistent() -> None:
    readiness_values = {
        "ready_now",
        "needs_columns",
        "needs_table",
        "needs_primitive_implementation",
        "needs_validator_implementation",
        "needs_primitive_and_validator",
        "needs_schema_and_primitive",
        "needs_schema_and_validator",
        "needs_schema_primitive_validator",
        "needs_primitive_parameter_support",
        "needs_custom_logic",
    }
    for item in expanded_scenario_items():
        assert item.score is not None
        component_total = (
            item.score.business_realism_score
            + item.score.data_model_fit_score
            + item.score.enterprise_relevance_score
            + item.score.detection_complexity_score
            + item.score.demo_value_score
            + item.score.training_value_score
        )
        assert item.score.total_score == component_total
        assert item.score.tier in {"A", "B", "C"}
        assert item.implementation_readiness in readiness_values
        assert item.execution_status in {"executable", "custom_reference", "specification_only"}
        if item.execution_status == "specification_only":
            assert item.implementation_readiness != "ready_now"
            assert item.implementation_dependencies.has_dependencies


def test_rejected_scenarios_are_separate_and_not_active() -> None:
    active_ids = {item.scenario_id for item in expanded_scenario_items()}
    rejected = load_rejected_scenario_library()["scenarios"]
    assert len(rejected) == 36
    assert all(item["status"] == "rejected" for item in rejected)
    assert all(item["rejected_reason"] for item in rejected)
    assert all(item["execution_status"] == "rejected" for item in rejected)
    assert not active_ids & {item["scenario_id"] for item in rejected}


def test_table_and_column_gaps_are_explicitly_marked() -> None:
    domain_catalog = load_domain_table_catalog()
    coverage = load_scenario_table_coverage()["coverage"]
    coverage_by_id = {item["scenario_id"]: item for item in coverage}
    assert len(coverage_by_id) == 760

    for item in expanded_scenario_items():
        row = coverage_by_id[item.scenario_id]
        assert row["table_support_status"] == item.table_support_status
        if item.table_support_status == "requires_new_table":
            assert item.proposed_tables
            proposed = {table["table_name"] for table in domain_catalog["proposed_tables"][item.domain]}
            assert set(item.proposed_tables) <= proposed
        if item.table_support_status == "requires_new_columns":
            assert item.proposed_columns


def test_mutation_and_validator_plans_cover_all_active_scenarios() -> None:
    active = expanded_scenario_items()
    primitive_plan = load_mutation_primitive_plan()["primitives"]
    validator_plan = load_validator_pattern_plan()["validator_patterns"]
    planned_primitives = {item["primitive_id"] for item in primitive_plan}
    planned_validators = {item["validator_pattern_id"] for item in validator_plan}
    assert {item.failure_primitive for item in active} <= planned_primitives
    assert {item.validator_pattern for item in active} <= planned_validators
    assert 25 <= len(planned_primitives) <= 40
    assert 15 <= len(planned_validators) <= 25


def test_all_yaml_catalogs_parse_successfully() -> None:
    catalog_files = [
        "dataforge/scenarios/catalog/scenario_taxonomy.yaml",
        "dataforge/scenarios/catalog/domain_table_catalog.yaml",
        "dataforge/scenarios/catalog/failure_taxonomy.yaml",
        "dataforge/scenarios/catalog/scenario_library.yaml",
        "dataforge/scenarios/catalog/rejected_scenarios.yaml",
        "dataforge/scenarios/catalog/scenario_table_coverage.yaml",
        "dataforge/scenarios/catalog/column_gap_analysis.yaml",
        "dataforge/scenarios/catalog/mutation_primitive_plan.yaml",
        "dataforge/scenarios/catalog/validator_pattern_plan.yaml",
        "dataforge/scenarios/catalog/scenario_library_coverage_report.yaml",
        "dataforge/scenarios/catalog/state_machines.yaml",
        "dataforge/scenarios/catalog/sla_policies.yaml",
        "dataforge/scenarios/catalog/business_policies.yaml",
        "dataforge/scenarios/catalog/column_blocker_report.yaml",
        "dataforge/scenarios/catalog/domain_column_semantics.yaml",
        "dataforge/scenarios/catalog/schema_leverage_report.yaml",
        "dataforge/scenarios/catalog/remaining_scenario_dependency_report.yaml",
        "dataforge/scenarios/catalog/scenario_performance_smoke_report.yaml",
        "dataforge/scenarios/catalog/scenario_quality_audit.yaml",
        "dataforge/scenarios/catalog/scenario_quality_summary.yaml",
        "dataforge/scenarios/catalog/failure_plan_contract.yaml",
        "dataforge/scenarios/catalog/ground_truth_contract.yaml",
        "dataforge/scenarios/catalog/scenario_configuration_contract.yaml",
    ]
    for path in catalog_files:
        with open(path, encoding="utf-8") as handle:
            assert yaml.safe_load(handle)
