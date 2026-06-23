from dataforge.domains.banking.generators import BankingGenerator
from dataforge.domains.banking.schemas import BANKING_SPEC
from dataforge.model import AUDIT_COLUMNS, TIME_HIERARCHY_COLUMNS
from dataforge.validation import schema_report, validate


def test_banking_generation_has_expected_tables_and_enterprise_columns():
    data = BankingGenerator(120, seed=81, load_type="bulk", scd_type=2).generate()
    assert set(data) == set(BANKING_SPEC.schemas)
    assert len(data["payments"]) == 120
    assert validate(data, BANKING_SPEC)["overall_status"] == "PASS"
    assert schema_report(data, BANKING_SPEC)["overall_status"] == "PASS"
    assert any(row["record_version"] == 2 for row in data["customers"])
    for table, rows in data.items():
        assert set(AUDIT_COLUMNS) <= set(rows[0])
        if table in BANKING_SPEC.fact_tables:
            assert set(TIME_HIERARCHY_COLUMNS) <= set(rows[0])


def test_banking_generation_includes_reconciliation_and_fraud_tags():
    data = BankingGenerator(300, seed=82).generate()
    assert any(row["is_fraud_scenario"] for row in data["payments"])
    assert any(row["is_reconciliation_scenario"] for row in data["payments"] + data["transfers"])
