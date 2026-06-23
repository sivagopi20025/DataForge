import json

import pytest

from dataforge.cli import main
from dataforge.domains.finance.generators import FinanceGenerator
from dataforge.domains.finance.schemas import FINANCE_SPEC
from dataforge.injector import FailureInjector
from dataforge.validation import validate


def test_finance_issue_injection_uses_shared_engine_for_selected_tables():
    clean = FinanceGenerator(80, seed=52).generate()
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
    injected, events = FailureInjector(rates, seed=52, spec=FINANCE_SPEC).apply(clean, {"transactions", "payments"})
    assert {event.table for event in events} <= {"transactions", "payments"}
    assert sum(event.count for event in events) > 0
    assert validate(injected, FINANCE_SPEC)["overall_status"] == "FAIL"


def test_finance_integration_generate_inject_validate_export_csv_json_parquet(tmp_path):
    pytest.importorskip("pyarrow")
    assert main([
        "--domain", "finance",
        "--records", "50",
        "--tables", "transactions", "payments",
        "--inject-failures", "true",
        "--failure-profile", "low",
        "--output-format", "csv", "json", "parquet",
        "--output", str(tmp_path),
        "--dataset-name", "finance-integration",
    ]) == 0
    run = next((tmp_path / "finance-integration").iterdir())
    assert (run / "bulk" / "transactions.csv").exists()
    assert (run / "bulk" / "transactions.json").exists()
    assert (run / "bulk" / "transactions.parquet").exists()
    assert (run / "bulk" / "payments.csv").exists()
    assert (run / "bulk" / "payments.json").exists()
    assert (run / "bulk" / "payments.parquet").exists()
    failures = json.loads((run / "failure_report.json").read_text())
    assert failures["total_injected"] > 0
