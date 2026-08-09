from __future__ import annotations

import yaml

from dataforge.scenarios.capability_analysis import build_capability_leverage_report


def test_capability_leverage_report_ranks_reusable_capabilities() -> None:
    report = yaml.safe_load(open("dataforge/scenarios/catalog/capability_leverage_report.yaml", encoding="utf-8"))
    assert report["baseline_counts"]["runtime_capable"] == 531
    assert report["after_batch_1_counts"]["runtime_capable"] == 151
    assert report["after_batch_2_counts"]["runtime_capable"] == 179
    assert report["after_batch_3_counts"]["runtime_capable"] == 264
    assert report["after_batch_4_counts"]["runtime_capable"] == 293
    assert report["after_batch_5_counts"]["runtime_capable"] == 439
    assert report["after_batch_6_counts"]["runtime_capable"] == 479
    assert report["after_batch_7_counts"]["runtime_capable"] == 507
    assert report["after_batch_8_counts"]["runtime_capable"] == 522
    assert report["after_batch_9_counts"]["runtime_capable"] == 531
    assert report["rankings"]["primitives"][0]["capability"] == "distribution_shift"
    assert report["rankings"]["validators"][0]["capability"] == "distribution_validator"


def test_batch_definitions_include_batch_2_reconciliation_scope() -> None:
    report = yaml.safe_load(open("dataforge/scenarios/catalog/capability_leverage_report.yaml", encoding="utf-8"))
    batches = report["implementation_batches"]
    assert [batch["batch"] for batch in batches] == [1, 2, 3, 5, 6, 7, 8, 9]
    assert batches[0]["primitives"] == ["timestamp_out_of_order", "sequence_gap", "duplicate_event"]
    assert batches[0]["validators"] == ["sequence_validator"]
    assert batches[0]["tables"] == []
    assert batches[0]["columns"] == []
    assert "cross_table_mismatch" in batches[1]["primitives"]
    assert "aggregate_mismatch" in batches[1]["primitives"]
    assert "cross_table_consistency_validator" in batches[1]["validators"]
    assert "aggregate_balance_validator" in batches[1]["validators"]
    assert "invalid_state_transition" in batches[2]["primitives"]
    assert "sla_validator" in batches[2]["validators"]
    assert "volume_anomaly_validator" in batches[2]["validators"]
    assert batches[3]["name"] == "domain_native_schema_reconciliation"
    assert batches[3]["metadata_only_newly_executable"] == 146
    assert batches[4]["name"] == "finance_schema_depth"
    assert batches[4]["newly_executable"] == 40
    assert batches[5]["name"] == "multi_domain_schema_depth"
    assert batches[5]["newly_executable"] == 28
    assert batches[6]["name"] == "banking_card_authorization_and_logistics_exception_depth"
    assert batches[6]["newly_executable"] == 15
    assert batches[7]["name"] == "scenario_v1_quality_audit_and_selective_manufacturing_depth"
    assert batches[7]["newly_executable"] == 9


def test_capability_report_builder_preserves_leverage_formula() -> None:
    report = build_capability_leverage_report(after_executable_count=151, after_batch_2_count=179, after_batch_3_count=264, after_batch_4_count=293, after_batch_5_count=439, after_batch_6_count=479, after_batch_7_count=507, after_batch_8_count=522, after_batch_9_count=531)
    assert "tier_a_scenarios*3" in report["leverage_score_formula"]
    assert report["rankings"]["primitives"]
    assert report["rankings"]["validators"]
