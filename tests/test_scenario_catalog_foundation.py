from __future__ import annotations

from dataforge.domains import DOMAIN_SPECS
from dataforge.scenarios import all_scenarios, find_scenarios
from dataforge.scenarios.catalog import (
    build_master_scenario_registry,
    load_domain_table_catalog,
    load_failure_taxonomy,
    load_scenario_taxonomy,
    validate_master_scenario_registry,
    validate_scenario_catalogs,
)
from dataforge.scenarios.catalog.loader import validate_master_scenario_registry as validate_registry_items
from dataforge.scenarios.catalog.models import MasterScenarioMetadata


def test_scenario_taxonomy_catalog_validates_against_runtime_domains() -> None:
    taxonomy = load_scenario_taxonomy()
    assert set(taxonomy["domains"]) == set(DOMAIN_SPECS)
    assert "duplication" in taxonomy["failure_categories"]
    assert "lifecycle_violation" in taxonomy["failure_categories"]
    assert {"low", "medium", "high", "critical", "stress"} <= set(taxonomy["severity_levels"])
    assert {"scenario_specific", "reconciliation", "streaming_event"} <= set(taxonomy["validator_categories"])
    assert validate_scenario_catalogs() == []


def test_domain_table_catalog_covers_every_supported_table() -> None:
    catalog = load_domain_table_catalog()
    for domain, spec in DOMAIN_SPECS.items():
        assert set(catalog["domains"][domain]) == set(spec.schemas)
        for table, schema in spec.schemas.items():
            table_catalog = catalog["domains"][domain][table]
            assert table_catalog["primary_key"] == schema.primary_key
            assert table_catalog["important_columns"]
            for foreign_key in schema.foreign_keys:
                assert foreign_key.column in table_catalog["foreign_keys"]


def test_failure_taxonomy_distinguishes_categories_from_primitives() -> None:
    taxonomy = load_failure_taxonomy()
    assert taxonomy["distinction"]["failure_category"]
    assert taxonomy["distinction"]["failure_primitive"]
    assert "duplicate_entity" in taxonomy["categories"]["duplication"]["primitives"]
    assert "schema_drift" in taxonomy["categories"]["data_format"]["primitives"]
    assert "temperature_threshold_breach" in taxonomy["categories"]["threshold_violation"]["primitives"]
    assert "dataforge.injector.FailureInjector" in taxonomy["existing_generic_implementation"]["module"]


def test_master_registry_maps_all_existing_50_scenarios() -> None:
    registry = build_master_scenario_registry()
    scenarios = all_scenarios()
    assert len(registry) == 50
    assert {item.scenario_id for item in registry} == {scenario.scenario_id for scenario in scenarios}
    assert validate_master_scenario_registry() == []
    assert sum(1 for item in registry if item.status == "reference_implemented") == 10


def test_master_registry_required_references_are_real() -> None:
    for item in build_master_scenario_registry():
        spec = DOMAIN_SPECS[item.domain]
        assert item.primary_table in spec.schemas
        assert all(table in spec.schemas for table in item.related_tables)
        assert all(any(column in schema.columns for schema in spec.schemas.values()) for column in item.required_columns)
        assert item.failure_category in load_scenario_taxonomy()["failure_categories"]


def test_catalog_validation_catches_duplicate_ids_unknown_domain_primitive_and_validator() -> None:
    valid = build_master_scenario_registry()[0]

    duplicate = (valid, valid)
    assert any("Duplicate scenario_id" in error for error in validate_registry_items(duplicate))

    unknown_domain = valid.model_copy(update={"domain": "unknown_domain"})
    assert any("unknown domain" in error for error in validate_registry_items((unknown_domain,)))

    unknown_primitive = valid.model_copy(update={"failure_primitive": "not_a_real_primitive"})
    assert any("unknown failure primitive" in error for error in validate_registry_items((unknown_primitive,)))

    unknown_table = valid.model_copy(update={"primary_table": "missing_table"})
    assert any("missing required table reference" in error for error in validate_registry_items((unknown_table,)))

    unknown_validator = valid.model_copy(update={"validator": "missing_validator", "validator_pattern": "reconciliation"})
    assert any("missing validator reference" in error for error in validate_registry_items((unknown_validator,)))


def test_master_registry_schema_rejects_invalid_severity_realism_and_difficulty() -> None:
    valid = build_master_scenario_registry()[0].model_dump()
    for field, value in [("severity", "urgent"), ("realism", "cinematic"), ("difficulty", "impossible")]:
        payload = {**valid, field: value}
        try:
            MasterScenarioMetadata.model_validate(payload)
        except Exception as exc:
            assert field in str(exc)
        else:  # pragma: no cover - defensive assertion for schema strictness
            raise AssertionError(f"{field} accepted invalid value {value}")


def test_existing_scenario_api_registry_behavior_remains_backward_compatible() -> None:
    assert len(all_scenarios()) == 50
    assert len(find_scenarios(domain="retail")) == 5
    assert find_scenarios(keyword="ghost provider")[0].scenario_id == "healthcare_ghost_provider"
