import json

import pytest

from dataforge.cli import main
from dataforge.domains.education.generators import EducationGenerator
from dataforge.domains.education.schemas import EDUCATION_SPEC
from dataforge.injector import FailureInjector
from dataforge.validation import validate


def test_education_issue_injection_uses_shared_engine_for_selected_tables():
    clean = EducationGenerator(80, seed=97).generate()
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
    injected, events = FailureInjector(rates, seed=97, spec=EDUCATION_SPEC).apply(clean, {"enrollments", "fees_payments"})
    assert {event.table for event in events} <= {"enrollments", "fees_payments"}
    assert sum(event.count for event in events) > 0
    assert validate(injected, EDUCATION_SPEC)["overall_status"] == "FAIL"


def test_education_integration_generate_inject_validate_export_csv_json_parquet(tmp_path):
    pytest.importorskip("pyarrow")
    assert main([
        "--domain", "education",
        "--records", "50",
        "--tables", "enrollments", "fees_payments",
        "--inject-failures", "true",
        "--failure-profile", "low",
        "--output-format", "csv", "json", "parquet",
        "--output", str(tmp_path),
        "--dataset-name", "education-integration",
    ]) == 0
    run = next((tmp_path / "education-integration").iterdir())
    assert (run / "bulk" / "enrollments.csv").exists()
    assert (run / "bulk" / "enrollments.json").exists()
    assert (run / "bulk" / "enrollments.parquet").exists()
    assert (run / "bulk" / "fees_payments.csv").exists()
    assert (run / "bulk" / "fees_payments.json").exists()
    assert (run / "bulk" / "fees_payments.parquet").exists()
    failures = json.loads((run / "failure_report.json").read_text())
    assert failures["total_injected"] > 0
