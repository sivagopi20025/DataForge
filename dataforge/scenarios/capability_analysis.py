from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import yaml

from dataforge.scenarios.catalog import expanded_scenario_items, load_domain_table_catalog


CATALOG_DIR = Path(__file__).resolve().parent / "catalog"


def _complexity(kind: str, capability: str) -> int:
    if kind == "parameters":
        return 1
    if kind == "columns":
        return 2
    if kind == "tables":
        return 5
    low_complexity = {
        "sequence_validator",
        "timestamp_out_of_order",
        "sequence_gap",
        "duplicate_event",
        "sla_validator",
        "value_below_threshold",
    }
    medium_complexity = {
        "aggregate_mismatch",
        "cross_table_mismatch",
        "aggregate_balance_validator",
        "cross_table_consistency_validator",
        "invalid_state_transition",
        "state_transition_validator",
        "volume_spike",
        "volume_drop",
        "volume_anomaly_validator",
    }
    if capability in low_complexity:
        return 2
    if capability in medium_complexity:
        return 3
    return 4


def _score(total: int, tier_a: int, domains: set[str], processes: set[str], complexity: int) -> int:
    return (total * 1) + (tier_a * 3) + (len(domains) * 5) + (len(processes) * 2) - (complexity * 3)


def _rank_capabilities(kind: str, dependency_key: str) -> list[dict[str, Any]]:
    buckets: dict[str, list[Any]] = defaultdict(list)
    for scenario in expanded_scenario_items():
        if scenario.execution_status != "specification_only":
            continue
        values = getattr(scenario.implementation_dependencies, dependency_key)
        if dependency_key == "unsupported_parameters":
            values = [f"parameter:{value}" for value in values]
        for value in values:
            buckets[value].append(scenario)

    rows: list[dict[str, Any]] = []
    for capability, scenarios in buckets.items():
        domains = {scenario.domain for scenario in scenarios}
        processes = {scenario.business_process for scenario in scenarios}
        tier_counts = Counter(scenario.score.tier for scenario in scenarios if scenario.score)
        complexity = _complexity(kind, capability.replace("parameter:", ""))
        rows.append(
            {
                "capability": capability,
                "total_blocked_scenarios": len(scenarios),
                "tier_a_scenarios": tier_counts.get("A", 0),
                "tier_b_scenarios": tier_counts.get("B", 0),
                "tier_c_scenarios": tier_counts.get("C", 0),
                "domains_affected": sorted(domains),
                "business_processes_affected": sorted(processes),
                "implementation_complexity": complexity,
                "leverage_score": _score(len(scenarios), tier_counts.get("A", 0), domains, processes, complexity),
                "example_scenarios": [scenario.scenario_id for scenario in scenarios[:10]],
            }
        )
    return sorted(rows, key=lambda item: item["leverage_score"], reverse=True)


def build_capability_leverage_report(
    *,
    after_executable_count: int | None = None,
    after_batch_2_count: int | None = None,
    after_batch_3_count: int | None = None,
    after_batch_4_count: int | None = None,
    after_batch_5_count: int | None = None,
    after_batch_6_count: int | None = None,
    after_batch_7_count: int | None = None,
    after_batch_8_count: int | None = None,
    after_batch_9_count: int | None = None,
) -> dict[str, Any]:
    items = expanded_scenario_items()
    before_counts = Counter(item.execution_status for item in items)
    domain_catalog = load_domain_table_catalog()
    primitive_rank = _rank_capabilities("primitives", "primitives")
    validator_rank = _rank_capabilities("validators", "validators")
    table_rank = _rank_capabilities("tables", "tables")
    column_rank = _rank_capabilities("columns", "columns")
    parameter_rank = _rank_capabilities("parameters", "unsupported_parameters")

    return {
        "version": "0.4.0",
        "purpose": "Rank blocked scenario capabilities by reusable execution leverage.",
        "leverage_score_formula": "total_scenarios + tier_a_scenarios*3 + domains_reused*5 + business_processes_reused*2 - implementation_complexity*3",
        "baseline_counts": {
            "total_registered": len(items),
            "executable": before_counts.get("executable", 0),
            "custom_reference": before_counts.get("custom_reference", 0),
            "runtime_capable": before_counts.get("executable", 0) + before_counts.get("custom_reference", 0),
            "specification_only": before_counts.get("specification_only", 0),
            "rejected": 36,
        },
        "after_batch_1_counts": {
            "runtime_capable": after_executable_count,
        },
        "after_batch_2_counts": {
            "runtime_capable": after_batch_2_count,
        },
        "after_batch_3_counts": {
            "runtime_capable": after_batch_3_count,
        },
        "after_batch_4_counts": {
            "runtime_capable": after_batch_4_count,
        },
        "after_batch_5_counts": {
            "runtime_capable": after_batch_5_count,
        },
        "after_batch_6_counts": {
            "runtime_capable": after_batch_6_count,
        },
        "after_batch_7_counts": {
            "runtime_capable": after_batch_7_count,
        },
        "after_batch_8_counts": {
            "runtime_capable": after_batch_8_count,
        },
        "after_batch_9_counts": {
            "runtime_capable": after_batch_9_count,
        },
        "rankings": {
            "primitives": primitive_rank,
            "validators": validator_rank,
            "tables": table_rank,
            "columns": column_rank,
            "parameters": parameter_rank,
        },
        "implementation_batches": [
            {
                "batch": 1,
                "name": "sequence_and_legacy_alias_unlock",
                "rationale": "Highest low-complexity runtime unlock: one generic validator, two sequence primitives, duplicate-event support, and harmless legacy alias parameter support.",
                "primitives": ["timestamp_out_of_order", "sequence_gap", "duplicate_event"],
                "validators": ["sequence_validator"],
                "parameters": ["legacy_runtime_primitive"],
                "tables": [],
                "columns": [],
                "expected_scenarios_to_become_executable": 71,
                "domains_affected": ["banking", "ecommerce", "education", "healthcare", "insurance", "logistics", "manufacturing", "retail", "telecommunications"],
                "estimated_implementation_complexity": "low",
            },
            {
                "batch": 2,
                "name": "cross_table_and_aggregate_reconciliation",
                "rationale": "High Tier-A/business value across all domains, but needs more careful validator semantics than Batch 1.",
                "primitives": ["cross_table_mismatch", "aggregate_mismatch"],
                "validators": ["cross_table_consistency_validator", "aggregate_balance_validator"],
                "tables": [],
                "columns": ["expected_amount", "actual_amount", "reconciliation_group_id"],
                "estimated_implementation_complexity": "medium",
            },
            {
                "batch": 3,
                "name": "state_sla_and_volume_anomaly",
                "rationale": "Broad workflow coverage that may require richer status/time/volume metadata and some schema expansion.",
                "primitives": ["invalid_state_transition", "stale_timestamp", "timeout_violation", "volume_spike", "volume_drop"],
                "validators": ["state_transition_validator", "sla_validator", "volume_anomaly_validator"],
                "tables": sorted({table["table_name"] for tables in domain_catalog.get("proposed_tables", {}).values() for table in tables})[:10],
                "columns": ["scenario_status_code", "event_timestamp", "reason_code"],
                "estimated_implementation_complexity": "medium-high",
            },
            {
                "batch": 5,
                "name": "domain_native_schema_reconciliation",
                "rationale": "Corrected domain-native semantic mappings for existing columns without adding broad new product behavior.",
                "primitives": [],
                "validators": [],
                "tables": [],
                "columns": ["domain-native amount/status/timestamp/reason/id semantics"],
                "metadata_only_newly_executable": 146,
                "estimated_implementation_complexity": "medium",
            },
            {
                "batch": 6,
                "name": "finance_schema_depth",
                "rationale": "Added high-leverage finance-native market, risk, trade, and position tables to unlock executable finance scenarios.",
                "primitives": [],
                "validators": [],
                "tables": ["finance.trades", "finance.market_data", "finance.positions", "finance.risk_events"],
                "columns": ["finance.positions.position_reason"],
                "newly_executable": 40,
                "estimated_implementation_complexity": "medium-high",
            },
            {
                "batch": 7,
                "name": "multi_domain_schema_depth",
                "rationale": "Added targeted high-leverage business tables across weaker domains instead of deepening one already-strong domain.",
                "primitives": [],
                "validators": [],
                "tables": [
                    "ecommerce.seller_payouts",
                    "education.academic_standing_events",
                    "healthcare.prior_authorizations",
                    "manufacturing.sensor_readings",
                ],
                "columns": [
                    "seller payout lifecycle fields",
                    "academic standing GPA/credit fields",
                    "prior authorization status/date/amount fields",
                    "machine sensor measurement/quality fields",
                ],
                "newly_executable": 28,
                "estimated_implementation_complexity": "medium-high",
            },
            {
                "batch": 8,
                "name": "banking_card_authorization_and_logistics_exception_depth",
                "rationale": "Added the two highest-leverage deferred business tables from Batch 7 to unlock Banking card workflows and Logistics exception workflows.",
                "primitives": [],
                "validators": [],
                "tables": ["banking.card_authorizations", "logistics.exception_alerts"],
                "columns": [
                    "banking card authorization lifecycle, amount, response, and reason fields",
                    "logistics exception alert lifecycle, severity, impact, and reason fields",
                ],
                "newly_executable": 15,
                "estimated_implementation_complexity": "medium",
            },
            {
                "batch": 9,
                "name": "scenario_v1_quality_audit_and_selective_manufacturing_depth",
                "rationale": "Paused pure unlock maximization to audit runtime-capable scenario quality, then added only Manufacturing-native operational columns needed to move the weakest domain above 60% runtime coverage.",
                "primitives": [],
                "validators": [],
                "tables": [],
                "columns": [
                    "manufacturing.production_lines.risk_score",
                    "manufacturing.production_lines.idempotency_key",
                    "manufacturing.suppliers.idempotency_key",
                    "manufacturing.work_orders.expected_amount",
                    "manufacturing.work_orders.actual_amount",
                    "manufacturing.work_orders.risk_score",
                    "manufacturing.work_orders.idempotency_key",
                    "manufacturing.quality_checks.scenario_status_code",
                    "manufacturing.quality_checks.risk_score",
                    "manufacturing.quality_checks.idempotency_key",
                    "manufacturing.factories.planned_capacity_amount",
                ],
                "newly_executable": 9,
                "quality_audit_runtime_capable": 531,
                "estimated_implementation_complexity": "medium",
            },
        ],
    }


def write_capability_leverage_report(
    path: Path | None = None,
    *,
    after_executable_count: int | None = None,
    after_batch_2_count: int | None = None,
    after_batch_3_count: int | None = None,
    after_batch_4_count: int | None = None,
    after_batch_5_count: int | None = None,
    after_batch_6_count: int | None = None,
    after_batch_7_count: int | None = None,
    after_batch_8_count: int | None = None,
    after_batch_9_count: int | None = None,
) -> dict[str, Any]:
    report = build_capability_leverage_report(
        after_executable_count=after_executable_count,
        after_batch_2_count=after_batch_2_count,
        after_batch_3_count=after_batch_3_count,
        after_batch_4_count=after_batch_4_count,
        after_batch_5_count=after_batch_5_count,
        after_batch_6_count=after_batch_6_count,
        after_batch_7_count=after_batch_7_count,
        after_batch_8_count=after_batch_8_count,
        after_batch_9_count=after_batch_9_count,
    )
    target = path or CATALOG_DIR / "capability_leverage_report.yaml"
    target.write_text(yaml.safe_dump(report, sort_keys=False), encoding="utf-8")
    return report


if __name__ == "__main__":
    write_capability_leverage_report()
