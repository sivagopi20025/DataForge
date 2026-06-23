from dataforge.domains.finance.generators import FinanceGenerator
from dataforge.domains.finance.schemas import FINANCE_SPEC
from dataforge.injector import FailureInjector
from dataforge.validation import schema_report, validate


def test_schema_drift_is_injectable_and_reported():
    clean = FinanceGenerator(30, seed=102).generate()
    drifted, events = FailureInjector({"schema_drift": 0.1}, seed=102, spec=FINANCE_SPEC).apply(clean, {"transactions"})
    event_types = {event.failure_type for event in events}
    assert "schema_drift_COLUMN_ADDED" in event_types
    assert "schema_drift_COLUMN_REMOVED" in event_types
    assert "schema_drift_COLUMN_RENAMED" in event_types
    assert "schema_drift_DATATYPE_CHANGED" in event_types
    assert "schema_drift_NULLABILITY_CHANGED" in event_types
    assert "schema_drift_COLUMN_ORDER_CHANGED" in event_types

    report = validate(drifted, FINANCE_SPEC, {"transactions"})
    failed_checks = {check["name"] for check in report["checks"] if check["status"] == "FAIL"}
    assert "schema_columns_match" in failed_checks
    assert "schema_column_order" in failed_checks
    assert "schema_renamed_column_suspected" in failed_checks
    assert report["issues"]

    schema = schema_report(drifted, FINANCE_SPEC, {"transactions"})
    table = schema["tables"][0]
    assert table["extra_columns"]
    assert table["missing_columns"]
    assert table["column_order_changed"] is True
