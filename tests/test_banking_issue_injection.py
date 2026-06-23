import json

import pytest

from dataforge.cli import main
from dataforge.domains.banking.generators import BankingGenerator
from dataforge.domains.banking.schemas import BANKING_SPEC
from dataforge.injector import FailureInjector
from dataforge.validation import validate


def test_banking_issue_injection_uses_shared_engine_for_selected_tables():
    clean = BankingGenerator(80, seed=94).generate()
    rates = {
        "null_values": 0.02,
        "duplicate_records": 0.02,
        "datatype_mismatch": 0.02,
        "foreign_key_break": 0.02,
        "invalid_dates": 0.02,
        "negative_values": 0.02,
        "outliers": 0.02,
        "missing_records": 0.01,
    }
    injected, events = FailureInjector(rates, seed=94, spec=BANKING_SPEC).apply(clean, {"payments", "transfers"})
    assert {event.table for event in events} <= {"payments", "transfers"}
    assert sum(event.count for event in events) > 0
    assert validate(injected, BANKING_SPEC)["overall_status"] == "FAIL"


def test_banking_integration_generate_inject_validate_export_csv_json_parquet(tmp_path):
    pytest.importorskip("pyarrow")
    assert main([
        "--domain", "banking",
        "--records", "50",
        "--tables", "payments", "transfers",
        "--inject-failures", "true",
        "--failure-profile", "low",
        "--output-format", "csv", "json", "parquet",
        "--output", str(tmp_path),
        "--dataset-name", "banking-integration",
    ]) == 0
    run = next((tmp_path / "banking-integration").iterdir())
    assert (run / "bulk" / "payments.csv").exists()
    assert (run / "bulk" / "payments.json").exists()
    assert (run / "bulk" / "payments.parquet").exists()
    assert (run / "bulk" / "transfers.csv").exists()
    assert (run / "bulk" / "transfers.json").exists()
    assert (run / "bulk" / "transfers.parquet").exists()
    failures = json.loads((run / "failure_report.json").read_text())
    assert failures["total_injected"] > 0
