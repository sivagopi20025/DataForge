from dataforge.domains.insurance.generators import InsuranceGenerator
from dataforge.domains.insurance.schemas import INSURANCE_SPEC
from dataforge.model import AUDIT_COLUMNS, TIME_HIERARCHY_COLUMNS
from dataforge.validation import schema_report, validate


def test_insurance_generation_has_expected_tables_and_enterprise_columns():
    data = InsuranceGenerator(120, seed=61, load_type="bulk", scd_type=2).generate()
    assert set(data) == set(INSURANCE_SPEC.schemas)
    assert len(data["claims"]) == 120
    assert validate(data, INSURANCE_SPEC)["overall_status"] == "PASS"
    assert schema_report(data, INSURANCE_SPEC)["overall_status"] == "PASS"
    assert any(row["record_version"] == 2 for row in data["customers"])
    for table, rows in data.items():
        assert set(AUDIT_COLUMNS) <= set(rows[0])
        if table in INSURANCE_SPEC.fact_tables:
            assert set(TIME_HIERARCHY_COLUMNS) <= set(rows[0])


def test_insurance_generation_includes_tagged_fraud_scenarios():
    data = InsuranceGenerator(250, seed=62).generate()
    assert any(row["is_fraud_scenario"] for row in data["claims"])
