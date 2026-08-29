from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from dataforge.domains import DOMAIN_SPECS
from dataforge.scenarios.catalog.models import MasterScenarioMetadata, ScenarioScore
from dataforge.scenarios.models import ScenarioDefinition
from dataforge.scenarios.registry import all_scenarios
from dataforge.scenarios.schema_semantics import COLUMN_SEMANTIC_RESOLVER
from dataforge.scenarios.validators import ScenarioValidatorRegistry


CATALOG_DIR = Path(__file__).resolve().parent
REFERENCE_SCENARIO_IDS = ScenarioValidatorRegistry().supported_scenarios()

ISSUE_TYPE_TO_FAILURE_CATEGORY = {
    "duplicate_records": "duplication",
    "null_values": "missing_data",
    "datatype_mismatch": "invalid_value",
    "invalid_dates": "temporal",
    "negative_values": "boundary_violation",
    "foreign_key_break": "referential_integrity",
    "schema_drift": "data_format",
    "outliers": "threshold_violation",
    "missing_records": "missing_data",
}

SCENARIO_CATEGORY_TO_FAILURE_CATEGORY = {
    "batch_processing": "temporal",
    "business_rule": "policy_violation",
    "data_quality": "invalid_value",
    "fraud_risk": "fraud_anomaly",
    "operational_failure": "availability",
    "performance": "volume_anomaly",
    "reconciliation": "aggregate_mismatch",
    "referential_integrity": "referential_integrity",
    "streaming": "volume_anomaly",
    "temporal_sequence": "sequence",
}

ISSUE_TYPE_TO_PRIMITIVE = {
    "duplicate_records": "duplicate_entity",
    "null_values": "set_required_value_null",
    "datatype_mismatch": "datatype_mismatch",
    "invalid_dates": "future_or_invalid_date",
    "negative_values": "negative_numeric_value",
    "foreign_key_break": "break_foreign_key",
    "schema_drift": "schema_drift",
    "outliers": "out_of_range_numeric_value",
    "missing_records": "remove_entity",
}

SCENARIO_PRIMITIVE_OVERRIDES = {
    "retail_payment_retry": "duplicate_retry",
    "banking_duplicate_transfer": "duplicate_transaction",
    "healthcare_ghost_provider": "orphan_child_record",
    "manufacturing_defect_spike": "defect_rate_spike",
    "telecom_tower_congestion": "dropped_call_rate_spike",
    "logistics_cold_chain_failure": "temperature_threshold_breach",
    "finance_settlement_delay": "settlement_delay",
    "insurance_coverage_exceeded": "coverage_limit_violation",
    "education_grade_calculation_error": "grade_formula_error",
    "ecommerce_inventory_oversell": "inventory_oversell",
}

SCENARIO_CATEGORY_TO_PROCESS = {
    "batch_processing": "batch_processing",
    "business_rule": "policy_and_rule_enforcement",
    "data_quality": "data_quality_control",
    "fraud_risk": "fraud_monitoring",
    "operational_failure": "operations",
    "performance": "capacity_and_performance",
    "reconciliation": "reconciliation",
    "referential_integrity": "master_data_management",
    "streaming": "streaming_operations",
    "temporal_sequence": "lifecycle_sequence",
}


class CatalogValidationError(ValueError):
    pass


def _load_yaml(filename: str) -> dict[str, Any]:
    path = CATALOG_DIR / filename
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


@lru_cache(maxsize=1)
def load_scenario_taxonomy() -> dict[str, Any]:
    return _load_yaml("scenario_taxonomy.yaml")


@lru_cache(maxsize=1)
def load_domain_table_catalog() -> dict[str, Any]:
    return _load_yaml("domain_table_catalog.yaml")


@lru_cache(maxsize=1)
def load_failure_taxonomy() -> dict[str, Any]:
    return _load_yaml("failure_taxonomy.yaml")


def failure_primitives() -> set[str]:
    taxonomy = load_failure_taxonomy()
    primitives: set[str] = set()
    for category in taxonomy.get("categories", {}).values():
        primitives.update(category.get("primitives", []))
    primitives.update(item.get("primitive_id") for item in taxonomy.get("primitive_catalog", []) if item.get("primitive_id"))
    return primitives


def validator_patterns() -> set[str]:
    taxonomy = load_scenario_taxonomy()
    patterns = set(taxonomy.get("validator_categories", []))
    patterns.update(taxonomy.get("validator_patterns", []))
    try:
        patterns.update(item.get("validator_pattern_id") for item in load_validator_pattern_plan().get("validator_patterns", []) if item.get("validator_pattern_id"))
    except FileNotFoundError:
        pass
    return patterns


@lru_cache(maxsize=1)
def load_expanded_scenario_library() -> dict[str, Any]:
    return _load_yaml("scenario_library.yaml")


@lru_cache(maxsize=1)
def load_rejected_scenario_library() -> dict[str, Any]:
    return _load_yaml("rejected_scenarios.yaml")


@lru_cache(maxsize=1)
def load_scenario_table_coverage() -> dict[str, Any]:
    return _load_yaml("scenario_table_coverage.yaml")


@lru_cache(maxsize=1)
def load_domain_column_semantics() -> dict[str, Any]:
    return _load_yaml("domain_column_semantics.yaml")


@lru_cache(maxsize=1)
def load_mutation_primitive_plan() -> dict[str, Any]:
    return _load_yaml("mutation_primitive_plan.yaml")


@lru_cache(maxsize=1)
def load_validator_pattern_plan() -> dict[str, Any]:
    return _load_yaml("validator_pattern_plan.yaml")


@lru_cache(maxsize=1)
def load_scenario_quality_audit() -> dict[str, Any]:
    return _load_yaml("scenario_quality_audit.yaml")


@lru_cache(maxsize=1)
def load_scenario_quality_summary() -> dict[str, Any]:
    return _load_yaml("scenario_quality_summary.yaml")


def build_master_metadata(scenario: ScenarioDefinition) -> MasterScenarioMetadata:
    failure = scenario.failure_injections[0]
    failure_category = ISSUE_TYPE_TO_FAILURE_CATEGORY.get(failure.issue_type) or SCENARIO_CATEGORY_TO_FAILURE_CATEGORY.get(scenario.category, "invalid_value")
    failure_primitive = SCENARIO_PRIMITIVE_OVERRIDES.get(scenario.scenario_id, ISSUE_TYPE_TO_PRIMITIVE.get(failure.issue_type, "replace_with_invalid_format"))
    primary_table = failure.table or scenario.primary_transaction_table
    related_tables = sorted(set([primary_table, *scenario.required_tables, *scenario.affected_tables]))
    required_columns = _required_columns(scenario, primary_table, related_tables)
    validator = "scenario_specific_validator" if scenario.scenario_id in REFERENCE_SCENARIO_IDS else scenario.expected_validations[0]
    validator_pattern = "scenario_specific" if scenario.scenario_id in REFERENCE_SCENARIO_IDS else _validator_pattern(scenario)
    return MasterScenarioMetadata(
        scenario_id=scenario.scenario_id,
        domain=scenario.domain,
        business_process=SCENARIO_CATEGORY_TO_PROCESS.get(scenario.category, scenario.category),
        entity=_entity_for_table(primary_table),
        scenario_name=scenario.name,
        description=scenario.detailed_description,
        failure_category=failure_category,
        failure_primitive=failure_primitive,
        primary_table=primary_table,
        related_tables=related_tables,
        required_columns=required_columns,
        business_rule=scenario.business_problem,
        mutation_strategy=failure.mutation_strategy,
        validator=validator,
        validator_pattern=validator_pattern,
        primitive_parameters=_default_primitive_parameters(scenario),
        validator_parameters=_default_validator_parameters(scenario),
        expected_evidence=_expected_evidence(scenario),
        severity=_canonical_severity(scenario.default_severity),
        realism="high" if "stress" in scenario.recommended_realism_profiles and "realistic" in scenario.recommended_realism_profiles else "realistic",
        difficulty="hard" if scenario.scenario_id in REFERENCE_SCENARIO_IDS else "medium",
        tags=scenario.tags,
        training_value=f"Useful for training users and future models to recognize {scenario.domain} {failure_category} failures in {scenario.category} workflows.",
        status="reference_implemented" if scenario.scenario_id in REFERENCE_SCENARIO_IDS else "implemented",
        version=scenario.version,
        score=ScenarioScore(
            business_realism_score=5,
            data_model_fit_score=5,
            enterprise_relevance_score=5 if scenario.scenario_id in REFERENCE_SCENARIO_IDS else 4,
            detection_complexity_score=4,
            demo_value_score=5 if scenario.scenario_id in REFERENCE_SCENARIO_IDS else 4,
            training_value_score=5,
            total_score=29 if scenario.scenario_id in REFERENCE_SCENARIO_IDS else 27,
            tier="A",
        ),
        implementation_readiness="ready_now",
        table_support_status="fully_supported",
    )


@lru_cache(maxsize=1)
def build_master_scenario_registry() -> tuple[MasterScenarioMetadata, ...]:
    return tuple(build_master_metadata(scenario) for scenario in all_scenarios())


def validate_scenario_catalogs() -> list[str]:
    errors: list[str] = []
    taxonomy = load_scenario_taxonomy()
    failure_taxonomy = load_failure_taxonomy()
    domain_catalog = load_domain_table_catalog()
    domain_names = set(DOMAIN_SPECS)

    if set(taxonomy.get("domains", [])) != domain_names:
        errors.append("scenario_taxonomy.yaml domains do not match DOMAIN_SPECS")
    missing_categories = set(taxonomy.get("failure_categories", [])) - set(failure_taxonomy.get("categories", {}))
    if missing_categories:
        errors.append(f"failure_taxonomy.yaml missing categories: {sorted(missing_categories)}")
    if set(domain_catalog.get("domains", {})) != domain_names:
        errors.append("domain_table_catalog.yaml domains do not match DOMAIN_SPECS")
    for domain, spec in DOMAIN_SPECS.items():
        catalog_tables = set(domain_catalog.get("domains", {}).get(domain, {}))
        if catalog_tables != set(spec.schemas):
            errors.append(f"domain_table_catalog.yaml table mismatch for {domain}")
    errors.extend(validate_master_scenario_registry())
    try:
        errors.extend(validate_expanded_scenario_library())
    except FileNotFoundError:
        pass
    return errors


def validate_master_scenario_registry(registry: tuple[MasterScenarioMetadata, ...] | None = None) -> list[str]:
    registry = registry or build_master_scenario_registry()
    errors: list[str] = []
    seen: set[str] = set()
    domains = set(load_scenario_taxonomy().get("domains", []))
    categories = set(load_scenario_taxonomy().get("failure_categories", []))
    primitives = failure_primitives()
    patterns = validator_patterns()
    scenario_ids_with_validators = REFERENCE_SCENARIO_IDS
    expected_validation_ids = {
        validation_id
        for scenario in all_scenarios()
        for validation_id in scenario.expected_validations
    }

    for item in registry:
        try:
            item = MasterScenarioMetadata.model_validate(item.model_dump())
        except ValidationError as exc:
            errors.append(str(exc))
            continue
        if item.scenario_id in seen:
            errors.append(f"Duplicate scenario_id: {item.scenario_id}")
        seen.add(item.scenario_id)
        if item.domain not in domains:
            errors.append(f"{item.scenario_id}: unknown domain {item.domain}")
            continue
        spec = DOMAIN_SPECS[item.domain]
        if item.failure_category not in categories:
            errors.append(f"{item.scenario_id}: unknown failure category {item.failure_category}")
        if item.failure_primitive not in primitives:
            errors.append(f"{item.scenario_id}: unknown failure primitive {item.failure_primitive}")
        if item.primary_table not in spec.schemas:
            errors.append(f"{item.scenario_id}: missing required table reference {item.primary_table}")
        for table in item.related_tables:
            if table not in spec.schemas:
                errors.append(f"{item.scenario_id}: missing related table reference {table}")
        tables = [table for table in [item.primary_table, *item.related_tables] if table in spec.schemas]
        for column in item.required_columns:
            if not COLUMN_SEMANTIC_RESOLVER.resolve_for_scenario_tables(item.domain, tables or [item.primary_table], column).resolved and not any(column in schema.columns for schema in spec.schemas.values()):
                errors.append(f"{item.scenario_id}: missing required column reference {column}")
        if item.validator_pattern not in patterns:
            errors.append(f"{item.scenario_id}: unknown validator pattern {item.validator_pattern}")
        if item.validator == "scenario_specific_validator" and item.scenario_id not in scenario_ids_with_validators:
            errors.append(f"{item.scenario_id}: missing scenario-specific validator implementation")
        if item.validator != "scenario_specific_validator" and item.validator not in expected_validation_ids:
            errors.append(f"{item.scenario_id}: missing validator reference {item.validator}")
    if len(registry) != len(all_scenarios()):
        errors.append("Master scenario registry does not map all existing scenarios")
    return errors


def expanded_scenario_items(include_rejected: bool = False) -> tuple[MasterScenarioMetadata, ...]:
    library = load_expanded_scenario_library()
    items = [MasterScenarioMetadata.model_validate(item) for item in library.get("scenarios", [])]
    if include_rejected:
        rejected = load_rejected_scenario_library()
        items.extend(MasterScenarioMetadata.model_validate(item) for item in rejected.get("scenarios", []))
    return tuple(items)


def validate_expanded_scenario_library() -> list[str]:
    errors: list[str] = []
    active = expanded_scenario_items(include_rejected=False)
    rejected = expanded_scenario_items(include_rejected=True)[len(active):]
    errors.extend(_validate_registry(active, expect_active=True))
    errors.extend(_validate_registry(rejected, expect_active=False))
    active_ids = {item.scenario_id for item in active}
    existing_ids = {scenario.scenario_id for scenario in all_scenarios()}
    if not existing_ids <= active_ids:
        errors.append(f"Expanded library missing existing scenario IDs: {sorted(existing_ids - active_ids)}")
    if not (700 <= len(active) <= 850):
        errors.append(f"Expanded active scenario count {len(active)} outside target range 700-850")
    return errors


def _validate_registry(registry: tuple[MasterScenarioMetadata, ...], *, expect_active: bool) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    domains = set(load_scenario_taxonomy().get("domains", []))
    domain_processes = load_scenario_taxonomy().get("domain_business_processes", {})
    categories = set(load_scenario_taxonomy().get("failure_categories", []))
    primitives = failure_primitives()
    patterns = validator_patterns()
    existing_validators = {validation_id for scenario in all_scenarios() for validation_id in scenario.expected_validations}
    existing_validators.add("scenario_specific_validator")
    for item in registry:
        if item.scenario_id in seen:
            errors.append(f"Duplicate scenario_id: {item.scenario_id}")
        seen.add(item.scenario_id)
        if expect_active and item.status == "rejected":
            errors.append(f"{item.scenario_id}: rejected scenario present in active registry")
        if not expect_active and item.status != "rejected":
            errors.append(f"{item.scenario_id}: non-rejected scenario present in rejected registry")
        if item.domain not in domains:
            errors.append(f"{item.scenario_id}: unknown domain {item.domain}")
            continue
        if item.business_process not in set(domain_processes.get(item.domain, [])):
            errors.append(f"{item.scenario_id}: invalid business process {item.business_process}")
        if item.failure_category not in categories:
            errors.append(f"{item.scenario_id}: unknown failure category {item.failure_category}")
        if item.failure_primitive not in primitives:
            errors.append(f"{item.scenario_id}: unknown failure primitive {item.failure_primitive}")
        if item.validator_pattern not in patterns:
            errors.append(f"{item.scenario_id}: unknown validator pattern {item.validator_pattern}")
        if item.validator not in existing_validators and not item.validator.endswith("_validator"):
            errors.append(f"{item.scenario_id}: missing validator reference {item.validator}")
        errors.extend(_validate_table_and_column_support(item))
        if not item.primitive_parameters:
            errors.append(f"{item.scenario_id}: missing primitive parameters")
        if not item.validator_parameters:
            errors.append(f"{item.scenario_id}: missing validator parameters")
        if item.score and item.score.tier == "Reject" and item.status != "rejected":
            errors.append(f"{item.scenario_id}: reject-tier scenario cannot be active")
    return errors


def _validate_table_and_column_support(item: MasterScenarioMetadata) -> list[str]:
    errors: list[str] = []
    if item.domain not in DOMAIN_SPECS:
        return errors
    spec = DOMAIN_SPECS[item.domain]
    missing_tables = [table for table in [item.primary_table, *item.related_tables] if table not in spec.schemas and table not in item.proposed_tables]
    if missing_tables:
        errors.append(f"{item.scenario_id}: table references must exist or be proposed: {missing_tables}")
    existing_tables = [table for table in [item.primary_table, *item.related_tables] if table in spec.schemas]
    missing_columns = [
        column
        for column in item.required_columns
        if not COLUMN_SEMANTIC_RESOLVER.resolve_for_scenario_tables(item.domain, existing_tables or [item.primary_table], column).resolved
        and not any(column in schema.columns for schema in spec.schemas.values())
        and column not in item.proposed_columns
    ]
    if missing_columns:
        errors.append(f"{item.scenario_id}: required columns must exist or be proposed: {missing_columns}")
    if item.table_support_status == "requires_new_table" and not item.proposed_tables:
        errors.append(f"{item.scenario_id}: requires_new_table must list proposed_tables")
    if item.table_support_status == "requires_new_columns" and not item.proposed_columns:
        errors.append(f"{item.scenario_id}: requires_new_columns must list proposed_columns")
    return errors


def _entity_for_table(table: str) -> str:
    if table.endswith("ies"):
        return f"{table[:-3]}y"
    if table.endswith("s"):
        return table[:-1]
    return table


def _required_columns(scenario: ScenarioDefinition, primary_table: str, related_tables: list[str]) -> list[str]:
    spec = DOMAIN_SPECS[scenario.domain]
    columns = set(scenario.affected_columns)
    for failure in scenario.failure_injections:
        if failure.column:
            columns.add(failure.column)
    for table in related_tables:
        schema = spec.schemas.get(table)
        if not schema:
            continue
        columns.add(schema.primary_key)
        columns.update(fk.column for fk in schema.foreign_keys)
    if primary_table in spec.schemas:
        columns.add(spec.schemas[primary_table].primary_key)
    return sorted(columns)


def _validator_pattern(scenario: ScenarioDefinition) -> str:
    if scenario.category == "referential_integrity":
        return "referential_integrity"
    if scenario.category == "reconciliation":
        return "reconciliation"
    if scenario.category == "temporal_sequence":
        return "temporal_sequence"
    if scenario.category == "streaming":
        return "streaming_event"
    if scenario.category in {"business_rule", "fraud_risk", "operational_failure"}:
        return "business_rule"
    if scenario.category == "performance":
        return "statistical"
    return "scenario_specific" if scenario.scenario_id in REFERENCE_SCENARIO_IDS else "schema"


def _expected_evidence(scenario: ScenarioDefinition) -> list[str]:
    evidence = ["affected_entities", "affected_tables", "expected_count", "detected_count", "reconciliation_status"]
    for validation in scenario.expected_validations:
        if "duplicate" in validation:
            evidence.append("duplicate identifiers")
        if "reconciliation" in validation or "mismatch" in validation:
            evidence.append("reconciliation deltas")
        if "sequence" in validation or "delay" in validation:
            evidence.append("timestamp sequence")
        if "provider" in validation or "foreign" in validation:
            evidence.append("orphan references")
        if "threshold" in validation or "exceeded" in validation:
            evidence.append("threshold breach values")
    return evidence


def _canonical_severity(value: str) -> str:
    return "high" if value == "stress" else value


def _default_primitive_parameters(scenario: ScenarioDefinition) -> dict[str, Any]:
    failure = scenario.failure_injections[0]
    params: dict[str, Any] = {"affected_rate_default": failure.requested_rate}
    if failure.table:
        params["table"] = failure.table
    if failure.column:
        params["column"] = failure.column
    if failure.table and failure.table in DOMAIN_SPECS[scenario.domain].schemas:
        params["id_column"] = DOMAIN_SPECS[scenario.domain].schemas[failure.table].primary_key
    params["selector"] = failure.deterministic_selector
    return params


def _default_validator_parameters(scenario: ScenarioDefinition) -> dict[str, Any]:
    failure = scenario.failure_injections[0]
    params: dict[str, Any] = {"expected_validation_ids": scenario.expected_validations}
    if failure.table:
        params["table"] = failure.table
    if failure.column:
        params["columns"] = [failure.column]
    return params
