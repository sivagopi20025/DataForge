from dataforge.domains.finance.generators import FinanceGenerator
from dataforge.domains.finance.schemas import FINANCE_SPEC
from dataforge.injector import FailureInjector
from dataforge.modes import build_artifacts
from dataforge.schema_drift import export_schema_versions
from dataforge.validation import schema_report, validate


def test_schema_drift_is_injectable_and_reported(tmp_path):
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
    assert report["quality_score"] == 100
    assert report["status"] == "PASS"

    schema = schema_report(drifted, FINANCE_SPEC, {"transactions"})
    table = schema["tables"][0]
    assert not table["extra_columns"]
    assert not table["missing_columns"]
    assert table["column_order_changed"] is False

    artifacts = build_artifacts(drifted, "bulk", 102, {"transactions"}, FINANCE_SPEC)
    diff = export_schema_versions(tmp_path, artifacts, ["csv"], FINANCE_SPEC, events)
    assert diff is not None
    assert (tmp_path / "schema_versions" / "v1" / "transactions.csv").exists()
    assert (tmp_path / "schema_versions" / "v2" / "transactions.csv").exists()
    assert (tmp_path / "reports" / "schema_diff.json").exists()
    assert diff["tables"]["transactions"]["changes"]
