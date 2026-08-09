from __future__ import annotations

from dataforge.domains import DOMAIN_SPECS
from dataforge.realism import SUPPORTED_REALISM_DOMAINS
from dataforge.scenarios.models import ScenarioDefinition, ScenarioRunConfig, ScenarioValidationResult
from dataforge.scenarios.registry import all_scenarios, get_scenario

ALLOWED_ISSUE_TYPES = {
    "null_values",
    "duplicate_records",
    "datatype_mismatch",
    "invalid_dates",
    "negative_values",
    "foreign_key_break",
    "schema_drift",
    "outliers",
    "missing_records",
}
ALLOWED_OUTPUT_FORMATS = {"csv", "json", "parquet", "database"}
ALLOWED_DATABASE_TYPES = {"postgresql", "mssql", "mysql"}
SEVERITY_RATES = {"low": 0.01, "medium": 0.03, "high": 0.05, "stress": 0.10}


def validate_catalog() -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    for scenario in all_scenarios():
        errors.extend(validate_definition(scenario))
        if scenario.scenario_id in seen:
            errors.append(f"Duplicate scenario_id: {scenario.scenario_id}")
        seen.add(scenario.scenario_id)
    return errors


def validate_definition(scenario: ScenarioDefinition) -> list[str]:
    errors: list[str] = []
    spec = DOMAIN_SPECS.get(scenario.domain)
    if not spec:
        return [f"{scenario.scenario_id}: unknown domain {scenario.domain}"]
    if scenario.primary_transaction_table not in spec.schemas:
        errors.append(f"{scenario.scenario_id}: invalid primary table {scenario.primary_transaction_table}")
    for table in set(scenario.affected_tables + scenario.required_tables):
        if table not in spec.schemas:
            errors.append(f"{scenario.scenario_id}: invalid table {table}")
    for column in scenario.affected_columns:
        if not any(column in schema.columns for schema in spec.schemas.values()):
            errors.append(f"{scenario.scenario_id}: invalid affected column {column}")
    for profile in scenario.recommended_realism_profiles:
        if profile not in {"basic", "realistic", "stress"} and scenario.domain not in SUPPORTED_REALISM_DOMAINS:
            errors.append(f"{scenario.scenario_id}: unsupported profile {profile}")
    if scenario.default_realism_profile not in scenario.recommended_realism_profiles:
        errors.append(f"{scenario.scenario_id}: default realism profile not recommended")
    if scenario.default_mode not in scenario.supported_modes and "both" not in scenario.supported_modes:
        errors.append(f"{scenario.scenario_id}: default mode not supported")
    for output_format in scenario.supported_output_formats:
        if output_format not in ALLOWED_OUTPUT_FORMATS:
            errors.append(f"{scenario.scenario_id}: invalid output format {output_format}")
    for failure in scenario.failure_injections:
        if failure.issue_type not in ALLOWED_ISSUE_TYPES:
            errors.append(f"{scenario.scenario_id}: unknown issue type {failure.issue_type}")
        if failure.table and failure.table not in spec.schemas:
            errors.append(f"{scenario.scenario_id}: failure table invalid {failure.table}")
        if failure.table and failure.column and failure.column not in spec.schemas[failure.table].columns:
            errors.append(f"{scenario.scenario_id}: failure column invalid {failure.table}.{failure.column}")
        if failure.expected_validation_id not in scenario.expected_validations:
            errors.append(f"{scenario.scenario_id}: failure expected validation not listed {failure.expected_validation_id}")
        if failure.requested_rate > 0.10:
            errors.append(f"{scenario.scenario_id}: failure rate exceeds safe default limit")
    return errors


def resolve_config(config: ScenarioRunConfig) -> ScenarioValidationResult:
    errors: list[str] = []
    warnings = list(config.warnings)
    try:
        scenario = get_scenario(config.scenario_id)
    except ValueError as error:
        return ScenarioValidationResult(status="FAIL", errors=[str(error)], warnings=warnings)

    mode = config.mode or scenario.default_mode
    output_format = config.output_format or scenario.supported_output_formats[0]
    severity = config.severity or scenario.default_severity
    records = scenario.default_record_count if config.records is None else config.records
    realism_profile = config.realism_profile or scenario.default_realism_profile
    domain = config.domain or scenario.domain

    if domain != scenario.domain:
        errors.append(f"Config domain {domain} does not match scenario domain {scenario.domain}")
    if mode not in scenario.supported_modes and "both" not in scenario.supported_modes:
        errors.append(f"Mode {mode} is not supported for {scenario.scenario_id}")
    if output_format not in scenario.supported_output_formats:
        errors.append(f"Output format {output_format} is not supported for {scenario.scenario_id}")
    if output_format == "database" and not config.database_type:
        errors.append("database_type is required when output_format is database")
    if config.database_type and config.database_type not in ALLOWED_DATABASE_TYPES:
        errors.append(f"Unsupported database_type {config.database_type}")
    if records < scenario.minimum_record_count:
        errors.append(f"records must be at least {scenario.minimum_record_count} for {scenario.scenario_id}")
    if records == 0:
        warnings.append("records=0 creates schema-only outputs; scenario failure execution will be skipped.")
    if mode == "batch" and (config.event_rate or config.duration_seconds or config.event_type_selection):
        errors.append("event_rate, duration_seconds, and event_type_selection are only valid for streaming scenarios")
    if mode == "streaming" and output_format != "json":
        errors.append("streaming scenarios currently require output_format=json")
    for variation_id in config.variation_ids:
        if variation_id not in {variation.variation_id for variation in scenario.supported_variations}:
            errors.append(f"Unsupported variation {variation_id}")
    for failure_id, override in config.failure_overrides.items():
        known = {failure.failure_id for failure in scenario.failure_injections}
        if failure_id not in known:
            errors.append(f"Unknown failure override {failure_id}")
        rate = override.get("rate", override.get("requested_rate"))
        if rate is not None and not (0 <= float(rate) <= 0.10):
            errors.append(f"Failure override {failure_id} rate must be between 0 and 0.10")

    resolved = config.model_copy(
        update={
            "scenario_version": config.scenario_version or scenario.version,
            "domain": domain,
            "mode": mode,
            "realism_profile": realism_profile,
            "records": records,
            "output_format": output_format,
            "severity": severity,
            "warnings": warnings,
        }
    )
    return ScenarioValidationResult(status="FAIL" if errors else "PASS", resolved_config=resolved if not errors else None, errors=errors, warnings=warnings)

