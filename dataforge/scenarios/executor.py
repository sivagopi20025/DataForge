from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from dataforge.scenarios.models import ScenarioDefinition, ScenarioRunConfig, scenario_to_dict
from dataforge.scenarios.registry import get_scenario
from dataforge.scenarios.validator import SEVERITY_RATES, resolve_config


def resolve_scenario_run(config: ScenarioRunConfig) -> tuple[ScenarioDefinition, ScenarioRunConfig]:
    result = resolve_config(config)
    if result.status != "PASS" or not result.resolved_config:
        raise ValueError("; ".join(result.errors))
    return get_scenario(config.scenario_id), result.resolved_config


def failure_rates_for_config(scenario: ScenarioDefinition, config: ScenarioRunConfig) -> dict[str, float]:
    if (config.records or 0) == 0:
        return {}
    severity_rate = SEVERITY_RATES[config.severity or scenario.default_severity]
    rates: dict[str, float] = {}
    for failure in scenario.failure_injections:
        rate = severity_rate
        override = config.failure_overrides.get(failure.failure_id, {})
        if "rate" in override:
            rate = float(override["rate"])
        if "requested_rate" in override:
            rate = float(override["requested_rate"])
        rates[failure.issue_type] = max(rates.get(failure.issue_type, 0.0), min(rate, 0.10))
    return rates


def selected_tables_for_config(scenario: ScenarioDefinition, config: ScenarioRunConfig) -> list[str]:
    if config.table_selection:
        return config.table_selection
    return sorted(set(scenario.required_tables + scenario.affected_tables))


def build_generation_payload(config: ScenarioRunConfig) -> dict[str, Any]:
    scenario, resolved = resolve_scenario_run(config)
    payload = {
        "domain": scenario.domain,
        "load_type": "event_stream" if resolved.mode == "streaming" else "bulk",
        "format": resolved.output_format or "csv",
        "database_type": resolved.database_type,
        "records": resolved.records,
        "selected_tables": selected_tables_for_config(scenario, resolved),
        "issues": failure_rates_for_config(scenario, resolved),
        "user_email": resolved.requested_by,
        "scenario_id": scenario.scenario_id,
        "scenario_run_config": resolved.model_dump(),
        "scenario_definition": scenario_to_dict(scenario),
        "expected_validations": {
            "scenario_id": scenario.scenario_id,
            "expected_validations": scenario.expected_validations,
            "expected_quality_status": scenario.expected_quality_status,
        },
        "scenario_execution_report": build_execution_report(scenario, resolved),
    }
    return payload


def build_execution_report(scenario: ScenarioDefinition, config: ScenarioRunConfig, actual_issue_counts: dict[str, int] | None = None) -> dict[str, Any]:
    actual_issue_counts = actual_issue_counts or {}
    expected_issue_counts = {
        failure.issue_type: {"rate": failure_rates_for_config(scenario, config).get(failure.issue_type, 0.0), "rule": failure.expected_detected_count_rule}
        for failure in scenario.failure_injections
    }
    return {
        "scenario_id": scenario.scenario_id,
        "scenario_version": scenario.version,
        "configuration": config.model_dump(),
        "expected_issue_counts": expected_issue_counts,
        "actual_issue_counts": actual_issue_counts,
        "detected_issue_counts": actual_issue_counts,
        "expected_validations": scenario.expected_validations,
        "passed_validations": [],
        "failed_validations": [],
        "reconciliation_result": "PENDING",
        "scenario_outcome": "PENDING",
        "warnings": config.warnings,
        "execution_timing": {"configured_at": datetime.now(timezone.utc).isoformat()},
    }
