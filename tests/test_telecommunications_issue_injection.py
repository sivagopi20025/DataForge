import json

import pytest

from dataforge.cli import main
from dataforge.domains.telecommunications.generators import TelecommunicationsGenerator
from dataforge.domains.telecommunications.schemas import TELECOMMUNICATIONS_SPEC
from dataforge.injector import FailureInjector
from dataforge.validation import validate


def test_telecommunications_issue_injection_uses_shared_engine_for_selected_tables():
    clean = TelecommunicationsGenerator(80, seed=87).generate()
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
    injected, events = FailureInjector(rates, seed=87, spec=TELECOMMUNICATIONS_SPEC).apply(clean, {"call_detail_records", "data_sessions"})
    assert {event.table for event in events} <= {"call_detail_records", "data_sessions"}
    assert sum(event.count for event in events) > 0
    assert validate(injected, TELECOMMUNICATIONS_SPEC)["overall_status"] == "FAIL"


def test_telecommunications_integration_generate_inject_validate_export_csv_json_parquet(tmp_path):
    pytest.importorskip("pyarrow")
    assert main([
        "--domain", "telecommunications",
        "--records", "50",
        "--tables", "call_detail_records", "data_sessions",
        "--inject-failures", "true",
        "--failure-profile", "low",
        "--output-format", "csv", "json", "parquet",
        "--output", str(tmp_path),
        "--dataset-name", "telecom-integration",
    ]) == 0
    run = next((tmp_path / "telecom-integration").iterdir())
    assert (run / "bulk" / "call_detail_records.csv").exists()
    assert (run / "bulk" / "call_detail_records.json").exists()
    assert (run / "bulk" / "call_detail_records.parquet").exists()
    assert (run / "bulk" / "data_sessions.csv").exists()
    assert (run / "bulk" / "data_sessions.json").exists()
    assert (run / "bulk" / "data_sessions.parquet").exists()
    failures = json.loads((run / "failure_report.json").read_text())
    assert failures["total_injected"] > 0
