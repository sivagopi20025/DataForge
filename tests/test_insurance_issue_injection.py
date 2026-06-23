import json

import pytest

from dataforge.cli import main
from dataforge.domains.insurance.generators import InsuranceGenerator
from dataforge.domains.insurance.schemas import INSURANCE_SPEC
from dataforge.injector import FailureInjector
from dataforge.validation import validate


def test_insurance_issue_injection_uses_shared_engine_for_selected_tables():
    clean = InsuranceGenerator(80, seed=72).generate()
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
    injected, events = FailureInjector(rates, seed=72, spec=INSURANCE_SPEC).apply(clean, {"claims", "settlements"})
    assert {event.table for event in events} <= {"claims", "settlements"}
    assert sum(event.count for event in events) > 0
    assert validate(injected, INSURANCE_SPEC)["overall_status"] == "FAIL"


def test_insurance_integration_generate_inject_validate_export_csv_json_parquet(tmp_path):
    pytest.importorskip("pyarrow")
    assert main([
        "--domain", "insurance",
        "--records", "50",
        "--tables", "claims", "settlements",
        "--inject-failures", "true",
        "--failure-profile", "low",
        "--output-format", "csv", "json", "parquet",
        "--output", str(tmp_path),
        "--dataset-name", "insurance-integration",
    ]) == 0
    run = next((tmp_path / "insurance-integration").iterdir())
    assert (run / "bulk" / "claims.csv").exists()
    assert (run / "bulk" / "claims.json").exists()
    assert (run / "bulk" / "claims.parquet").exists()
    assert (run / "bulk" / "settlements.csv").exists()
    assert (run / "bulk" / "settlements.json").exists()
    assert (run / "bulk" / "settlements.parquet").exists()
    failures = json.loads((run / "failure_report.json").read_text())
    assert failures["total_injected"] > 0
