from dataforge.domains.finance.generators import FinanceGenerator
from dataforge.domains.finance.schemas import FINANCE_SPEC
from dataforge.model import AUDIT_COLUMNS, TIME_HIERARCHY_COLUMNS
from dataforge.validation import schema_report, validate


def test_finance_generation_has_expected_tables_and_enterprise_columns():
    data = FinanceGenerator(120, seed=41, load_type="bulk", scd_type=2).generate()
    assert set(data) == set(FINANCE_SPEC.schemas)
    assert len(data["transactions"]) == 120
    assert validate(data, FINANCE_SPEC)["overall_status"] == "PASS"
    assert schema_report(data, FINANCE_SPEC)["overall_status"] == "PASS"
    assert any(row["record_version"] == 2 for row in data["customers"])
    for table, rows in data.items():
        assert set(AUDIT_COLUMNS) <= set(rows[0])
        if table in FINANCE_SPEC.fact_tables:
            assert set(TIME_HIERARCHY_COLUMNS) <= set(rows[0])


def test_finance_generation_includes_tagged_fraud_scenarios():
    data = FinanceGenerator(250, seed=42).generate()
    assert any(row["is_fraud_scenario"] for row in data["transactions"])
