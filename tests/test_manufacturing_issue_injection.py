import json

import pytest

from dataforge.cli import main
from dataforge.domains.manufacturing.generators import ManufacturingGenerator
from dataforge.domains.manufacturing.schemas import MANUFACTURING_SPEC
from dataforge.injector import FailureInjector
from dataforge.validation import validate


def test_manufacturing_issue_injection_uses_shared_engine_for_selected_tables():
    clean = ManufacturingGenerator(80, seed=77).generate()
    rates = {
        "null_values": 0.02,
        "duplicate_records": 0.02,
        "datatype_mismatch": 0.02,
        "foreign_key_break": 0.02,
        "invalid_dates": 0.02,
        "negative_values": 0.02,
        "schema_drift": 0.02,
        "outliers": 0.02,
        "missing_records": 0.01,
    }
    injected, events = FailureInjector(rates, seed=77, spec=MANUFACTURING_SPEC).apply(clean, {"work_orders", "production_batches"})
    assert {event.table for event in events} <= {"work_orders", "production_batches"}
    assert sum(event.count for event in events) > 0
    assert validate(injected, MANUFACTURING_SPEC)["overall_status"] == "FAIL"


def test_manufacturing_integration_generate_inject_validate_export_csv_json_parquet(tmp_path):
    pytest.importorskip("pyarrow")
    assert main([
        "--domain", "manufacturing",
        "--records", "50",
        "--tables", "work_orders", "production_batches",
        "--inject-failures", "true",
        "--failure-profile", "low",
        "--output-format", "csv", "json", "parquet",
        "--output", str(tmp_path),
        "--dataset-name", "manufacturing-integration",
    ]) == 0
    run = next((tmp_path / "manufacturing-integration").iterdir())
    assert (run / "bulk" / "work_orders.csv").exists()
    assert (run / "bulk" / "work_orders.json").exists()
    assert (run / "bulk" / "work_orders.parquet").exists()
    assert (run / "bulk" / "production_batches.csv").exists()
    assert (run / "bulk" / "production_batches.json").exists()
    assert (run / "bulk" / "production_batches.parquet").exists()
    failures = json.loads((run / "failure_report.json").read_text())
    assert failures["total_injected"] > 0
