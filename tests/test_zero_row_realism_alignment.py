from __future__ import annotations

import csv
import json

import pytest

from dataforge.canonical import canonical_metadata, empty_dataset
from dataforge.cli import main
from dataforge.domains import DOMAIN_SPECS
from dataforge.injector import FailureInjector
from dataforge.modes import build_artifacts
from dataforge.schema_drift import export_schema_versions
from dataforge.validation import validate


@pytest.mark.parametrize("domain", sorted(DOMAIN_SPECS))
def test_zero_row_clean_data_passes_for_every_domain(domain):
    spec = DOMAIN_SPECS[domain]
    data = empty_dataset(spec)
    report = validate(data, spec, set(spec.schemas), record_count=0)

    assert set(data) == set(spec.schemas)
    assert all(rows == [] for rows in data.values())
    assert report["quality_score"] == 100
    assert report["status"] == "PASS"
    assert report["summary"]["failed"] == 0


@pytest.mark.parametrize("output_format", ["csv", "json", "parquet"])
def test_zero_row_cli_writes_schema_valid_files(output_format, tmp_path):
    if output_format == "parquet":
        pytest.importorskip("pyarrow")

    assert main(["--domain", "retail", "--records", "0", "--output-format", output_format, "--output", str(tmp_path), "--dataset-name", f"zero-{output_format}"]) == 0
    run = next((tmp_path / f"zero-{output_format}").iterdir())
    spec = DOMAIN_SPECS["retail"]
    sales_path = run / "bulk" / f"sales.{output_format}"

    assert sales_path.exists()
    if output_format == "csv":
        with sales_path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.reader(handle))
        assert rows == [list(spec.schemas["sales"].columns)]
    elif output_format == "json":
        assert json.loads(sales_path.read_text(encoding="utf-8")) == []
    else:
        import pyarrow.parquet as pq

        table = pq.read_table(sales_path)
        assert table.num_rows == 0
        assert table.column_names == list(spec.schemas["sales"].columns)

    quality = json.loads((run / "quality_report.json").read_text(encoding="utf-8"))
    alignment = json.loads((run / "alignment_report.json").read_text(encoding="utf-8"))
    realism = json.loads((run / "realism_report.json").read_text(encoding="utf-8"))
    assert quality["quality_score"] == 100
    assert alignment["status"] == "PASS"
    assert realism["no_public_rows_copied"] is True


def test_zero_row_failure_injection_is_skipped_and_documented(tmp_path):
    assert main(["--domain", "retail", "--records", "0", "--inject-failures", "true", "--output", str(tmp_path), "--dataset-name", "zero-injected"]) == 0
    run = next((tmp_path / "zero-injected").iterdir())
    failure_report = json.loads((run / "failure_report.json").read_text(encoding="utf-8"))
    skip_report = json.loads((run / "issue_skip_report.json").read_text(encoding="utf-8"))

    assert failure_report["total_injected"] == 0
    assert skip_report["status"] == "SKIPPED"
    assert "records=0" in skip_report["reason"]


def test_canonical_metadata_contains_reference_profiles_for_all_domains():
    for domain, spec in DOMAIN_SPECS.items():
        metadata = canonical_metadata(spec)
        assert metadata.primary_transaction_table in spec.schemas
        assert metadata.source_references
        assert all(source["no_copied_rows"] for source in metadata.source_references)
        assert {"basic", "realistic", "stress"} <= set(metadata.realism_profiles)


def test_schema_drift_exports_v1_v2_without_mutating_ordinary_output(tmp_path):
    spec = DOMAIN_SPECS["retail"]
    clean = __import__("dataforge.domains.retail.generators", fromlist=["RetailGenerator"]).RetailGenerator(25, seed=5).generate()
    injected, failures = FailureInjector({"schema_drift": 0.1}, seed=5, spec=spec).apply(clean, {"customers"})
    artifacts = build_artifacts(injected, "bulk", 5, {"customers"}, spec)
    diff = export_schema_versions(tmp_path, artifacts, ["csv", "json"], spec, failures)

    assert injected["customers"][0].keys() == clean["customers"][0].keys()
    assert diff is not None
    assert (tmp_path / "schema_versions" / "v1" / "customers.csv").exists()
    assert (tmp_path / "schema_versions" / "v2" / "customers.csv").exists()
    assert (tmp_path / "reports" / "schema_diff.json").exists()


def test_issue_manifest_events_include_alignment_fields():
    spec = DOMAIN_SPECS["retail"]
    clean = __import__("dataforge.domains.retail.generators", fromlist=["RetailGenerator"]).RetailGenerator(100, seed=7).generate()
    _, failures = FailureInjector({"foreign_key_break": 0.03, "duplicate_records": 0.03}, seed=7, spec=spec).apply(clean, {"sales"})

    assert failures
    for event in failures:
        if event.failure_type.startswith("schema_drift"):
            continue
        assert "eligible_row_count" in event.details
        assert "selected_row_count" in event.details
        assert "seed" in event.details
        assert event.count <= event.details["eligible_row_count"]

