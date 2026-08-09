import json

import pytest

from dataforge.cli import main
from dataforge.domains.ecommerce.generators import EcommerceGenerator
from dataforge.domains.ecommerce.schemas import ECOMMERCE_SPEC
from dataforge.injector import FailureInjector
from dataforge.validation import validate


def test_ecommerce_issue_injection_uses_shared_engine_for_selected_tables():
    clean = EcommerceGenerator(80, seed=107).generate()
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
    injected, events = FailureInjector(rates, seed=107, spec=ECOMMERCE_SPEC).apply(clean, {"orders", "payments"})
    assert {event.table for event in events} <= {"orders", "payments"}
    assert sum(event.count for event in events) > 0
    assert validate(injected, ECOMMERCE_SPEC)["overall_status"] == "FAIL"


def test_ecommerce_integration_generate_inject_validate_export_csv_json_parquet(tmp_path):
    pytest.importorskip("pyarrow")
    assert main([
        "--domain", "ecommerce",
        "--records", "50",
        "--tables", "orders", "payments",
        "--inject-failures", "true",
        "--failure-profile", "low",
        "--output-format", "csv", "json", "parquet",
        "--output", str(tmp_path),
        "--dataset-name", "ecommerce-integration",
    ]) == 0
    run = next((tmp_path / "ecommerce-integration").iterdir())
    assert (run / "bulk" / "orders.csv").exists()
    assert (run / "bulk" / "orders.json").exists()
    assert (run / "bulk" / "orders.parquet").exists()
    assert (run / "bulk" / "payments.csv").exists()
    assert (run / "bulk" / "payments.json").exists()
    assert (run / "bulk" / "payments.parquet").exists()
    failures = json.loads((run / "failure_report.json").read_text())
    assert failures["total_injected"] > 0
