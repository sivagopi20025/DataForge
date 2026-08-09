import csv
import json
from datetime import datetime, timezone

import pytest

from dataforge.cli import create_run_directory, main
from dataforge.domains.logistics.generators import LogisticsGenerator
from dataforge.domains.logistics.schemas import LOGISTICS_SPEC
from dataforge.generator import RetailGenerator
from dataforge.injector import FailureInjector
from dataforge.model import AUDIT_COLUMNS, FACT_TABLES, SCHEMAS, TIME_HIERARCHY_COLUMNS
from dataforge.modes import build_artifacts
from dataforge.validation import reconciliation_report, relationship_report, schema_report, validate


def test_clean_dataset_has_enterprise_contract_and_valid_relationships():
    data = RetailGenerator(200, seed=7, load_type="bulk", scd_type=2).generate()
    assert set(data) == set(SCHEMAS)
    assert len(data["sales"]) == 200
    assert validate(data)["overall_status"] == "PASS"
    assert relationship_report(data)["overall_status"] == "PASS"
    assert schema_report(data)["overall_status"] == "PASS"
    assert reconciliation_report(data)["overall_status"] == "PASS"
    assert any(row["record_version"] == 2 for row in data["customers"])
    assert any(row["is_current"] is False for row in data["customers"])
    for table, rows in data.items():
        assert set(AUDIT_COLUMNS) <= set(rows[0])
        if table in FACT_TABLES:
            assert set(TIME_HIERARCHY_COLUMNS) <= set(rows[0])


def test_injected_dataset_is_reproducible_and_fails_validation():
    clean = RetailGenerator(500, seed=9).generate()
    rates = {name: 0.02 for name in ("nulls", "duplicates", "datatype_mismatch", "fk_break", "invalid_dates", "negative_values", "outliers")}
    first, events = FailureInjector(rates, seed=9).apply(clean)
    second, _ = FailureInjector(rates, seed=9).apply(clean)
    assert first == second
    assert sum(event.count for event in events) > 0
    assert validate(first)["overall_status"] == "FAIL"


def test_foreign_key_break_respects_configured_rate():
    clean = RetailGenerator(1000, seed=19).generate()
    injected, events = FailureInjector({"foreign_key_break": 0.05}, seed=19).apply(clean, {"sales"})
    valid_store_ids = {row["store_id"] for row in clean["stores"]}
    broken_sales_rows = [row for row in injected["sales"] if row["store_id"] not in valid_store_ids]
    fk_events = [event for event in events if event.failure_type == "foreign_key_break" and event.table == "sales"]

    assert len(fk_events) == 1
    assert fk_events[0].count == 50
    assert fk_events[0].details["requested_rate"] == 0.05
    assert len(broken_sales_rows) == 50
    assert len(broken_sales_rows) < len(injected["sales"])


def test_schema_drift_does_not_recreate_renamed_column_as_blank_null_target():
    clean = RetailGenerator(100, seed=20).generate()
    injected, events = FailureInjector({"schema_drift": 0.05, "null_values": 0.05}, seed=20).apply(clean, {"customers"})
    renamed_events = [event for event in events if event.failure_type == "schema_drift_COLUMN_RENAMED" and event.table == "customers"]

    assert renamed_events
    renamed_from = renamed_events[0].column
    renamed_to = renamed_events[0].details["renamed_to"]
    assert renamed_to not in injected["customers"][0]
    assert renamed_from in injected["customers"][0]
    assert injected["customers"][0].keys() == clean["customers"][0].keys()


@pytest.mark.parametrize(
    ("load_type", "expected_prefix", "expected_count"),
    [
        ("bulk", "bulk/", 13),
        ("incremental", "incremental/day_", 39),
        ("delta", "delta/", 13),
        ("cdc", "cdc/sales_cdc", 1),
        ("event", "events/", 6),
    ],
)
def test_load_modes_are_mutually_exclusive(load_type, expected_prefix, expected_count):
    data = RetailGenerator(100, seed=3, load_type=load_type).generate()
    artifacts = build_artifacts(data, load_type, seed=3)
    assert len(artifacts) == expected_count
    assert all(name.startswith(expected_prefix) for name in artifacts)


def test_cli_exports_timestamped_run_and_all_reports(tmp_path):
    assert main(["--records", "100", "--output", str(tmp_path), "--inject-failures", "true", "--failure-profile", "low"]) == 0
    run_directories = list((tmp_path / "sample").glob("sample_*"))
    assert len(run_directories) == 1
    run_directory = run_directories[0]
    for table in SCHEMAS:
        assert (run_directory / "bulk" / f"{table}.csv").exists()
    for report in (
        "metadata.json",
        "quality_report.json",
        "failure_report.json",
        "relationship_report.json",
        "schema_report.json",
        "reconciliation_report.json",
        "validation_report.json",
        "issue_manifest.json",
        "run_summary.json",
        "alignment_report.json",
        "realism_report.json",
        "README.md",
    ):
        assert (run_directory / report).exists()
    metadata = json.loads((run_directory / "metadata.json").read_text())
    failures = json.loads((run_directory / "failure_report.json").read_text())
    summary = json.loads((run_directory / "run_summary.json").read_text())
    realism = json.loads((run_directory / "realism_report.json").read_text())
    readme = (run_directory / "README.md").read_text()
    assert metadata["artifacts"]["bulk/sales.csv"]["rows"] >= 100
    assert metadata["run_id"] == run_directory.name
    assert summary["realism_profile"] == "realistic"
    assert realism["engine"]["overall_realism_status"] == "PASS"
    assert "No public/reference dataset rows are copied" in readme
    assert failures["total_injected"] > 0
    with (run_directory / "bulk" / "sales.csv").open() as handle:
        assert len(list(csv.DictReader(handle))) >= 100


@pytest.mark.parametrize("records", ["-1"])
def test_cli_rejects_non_positive_records_cleanly(records, tmp_path, capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(["--records", records, "--output", str(tmp_path)])

    captured = capsys.readouterr()
    assert exc_info.value.code != 0
    assert "Error: argument --records: records must be at least 0" in captured.err
    assert "Traceback" not in captured.err
    assert not any(tmp_path.iterdir())


def test_cli_invalid_domain_reports_cleanly(tmp_path, capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(["--domain", "unknown", "--records", "10", "--output", str(tmp_path)])

    captured = capsys.readouterr()
    assert exc_info.value.code != 0
    assert "Error: argument --domain: invalid choice" in captured.err
    assert "Traceback" not in captured.err
    assert not any(tmp_path.iterdir())


def test_cli_valid_generation_still_works_after_boundary_validation(tmp_path):
    assert main(["--records", "1", "--tables", "sales", "--output", str(tmp_path), "--dataset-name", "valid-boundary"]) == 0
    run = next((tmp_path / "valid-boundary").iterdir())
    assert (run / "bulk" / "sales.csv").exists()


def test_json_export_and_run_directory_name(tmp_path):
    assert main(["--records", "20", "--load-type", "cdc", "--output-format", "json", "--output", str(tmp_path), "--dataset-name", "retail-cdc"]) == 0
    run = next((tmp_path / "retail-cdc").iterdir())
    assert (run / "cdc" / "sales_cdc.json").exists()
    path = create_run_directory(tmp_path, "retail", datetime(2026, 1, 2, 3, 4, 5, 6, tzinfo=timezone.utc))
    assert path.name == "retail_20260102T030405000006Z"


def test_parquet_export_supports_nullable_foreign_keys(tmp_path):
    pytest.importorskip("pyarrow")
    assert main(["--records", "20", "--output-format", "parquet", "--output", str(tmp_path), "--dataset-name", "retail-parquet"]) == 0
    run = next((tmp_path / "retail-parquet").iterdir())
    assert (run / "bulk" / "sales.parquet").exists()


def test_single_table_can_be_exported_as_csv_and_json(tmp_path):
    assert main(["--records", "30", "--tables", "sales", "--output-format", "csv", "json", "--output", str(tmp_path), "--dataset-name", "single"]) == 0
    run = next((tmp_path / "single").iterdir())
    assert (run / "bulk" / "sales.csv").exists()
    assert (run / "bulk" / "sales.json").exists()
    assert not (run / "bulk" / "customers.csv").exists()


def test_selected_table_list_only_exports_requested_files(tmp_path):
    assert main(["--records", "30", "--tables", "customers,products", "sales", "--output", str(tmp_path), "--dataset-name", "selected"]) == 0
    run = next((tmp_path / "selected").iterdir())
    assert {path.name for path in (run / "bulk").iterdir()} == {"customers.csv", "products.csv", "sales.csv"}
    metadata = json.loads((run / "metadata.json").read_text())
    assert metadata["selected_tables"] == ["customers", "products", "sales"]


def test_incremental_selection_applies_to_each_day():
    data = RetailGenerator(30, seed=4, load_type="incremental").generate()
    artifacts = build_artifacts(data, "incremental", seed=4, selected_tables={"sales"})
    assert set(artifacts) == {"incremental/day_1/sales", "incremental/day_2/sales", "incremental/day_3/sales"}


def test_failures_are_injected_only_into_selected_non_sales_table():
    clean = RetailGenerator(50, seed=12).generate()
    rates = {name: 0.02 for name in ("nulls", "duplicates", "datatype_mismatch", "fk_break", "invalid_dates", "negative_values", "outliers")}
    injected, events = FailureInjector(rates, seed=12).apply(clean, {"customers"})
    assert {event.table for event in events} == {"customers"}
    assert injected["sales"] == clean["sales"]
    assert len(injected["customers"]) > len(clean["customers"])
    assert validate(injected)["overall_status"] == "FAIL"


def test_selected_json_failure_report_matches_exported_table(tmp_path):
    assert main(["--records", "40", "--tables", "customers", "--inject-failures", "true", "--output-format", "json", "--output", str(tmp_path), "--dataset-name", "customer-failures"]) == 0
    run = next((tmp_path / "customer-failures").iterdir())
    rows = json.loads((run / "bulk" / "customers.json").read_text())
    report = json.loads((run / "failure_report.json").read_text())
    assert rows
    assert report["total_injected"] > 0
    assert {event["table"] for event in report["events"]} == {"customers"}


def test_cdc_payload_preserves_injected_sales_fields():
    clean = RetailGenerator(50, seed=13, load_type="cdc").generate()
    rates = {"datatype_mismatch": 0.1}
    injected, _ = FailureInjector(rates, seed=13).apply(clean, {"sales"})
    artifacts = build_artifacts(injected, "cdc", seed=13, selected_tables={"sales"})
    payloads = [row["after_value"] or row["before_value"] for row in artifacts["cdc/sales_cdc"]]
    assert any("999999" in payload for payload in payloads)


def test_logistics_dataset_has_valid_relationships_and_business_rules():
    data = LogisticsGenerator(120, seed=21, load_type="bulk", scd_type=2).generate()
    assert set(data) == set(LOGISTICS_SPEC.schemas)
    assert len(data["shipments"]) == 120
    assert validate(data, LOGISTICS_SPEC)["overall_status"] == "PASS"
    assert relationship_report(data, LOGISTICS_SPEC)["overall_status"] == "PASS"
    assert schema_report(data, LOGISTICS_SPEC)["overall_status"] == "PASS"
    assert reconciliation_report(data, LOGISTICS_SPEC)["overall_status"] == "PASS"


def test_logistics_cli_exports_selected_json_and_csv(tmp_path):
    assert main(["--domain", "logistics", "--records", "40", "--tables", "shipments", "tracking_events", "--output-format", "csv", "json", "--output", str(tmp_path), "--dataset-name", "logistics-selected"]) == 0
    run = next((tmp_path / "logistics-selected").iterdir())
    assert (run / "bulk" / "shipments.csv").exists()
    assert (run / "bulk" / "shipments.json").exists()
    assert (run / "bulk" / "tracking_events.csv").exists()
    assert not (run / "bulk" / "customers.csv").exists()
    metadata = json.loads((run / "metadata.json").read_text())
    assert metadata["domain"] == "logistics"


def test_logistics_cdc_and_event_stream_are_domain_driven():
    data = LogisticsGenerator(30, seed=22, load_type="event_stream").generate()
    cdc = build_artifacts(data, "cdc", seed=22, selected_tables={"shipments"}, spec=LOGISTICS_SPEC)
    events = build_artifacts(data, "event_stream", seed=22, selected_tables={"tracking_events", "gps_events"}, spec=LOGISTICS_SPEC)
    assert set(cdc) == {"cdc/shipments_cdc"}
    assert {"events/tracking_event", "events/gps_event"} <= set(events)
