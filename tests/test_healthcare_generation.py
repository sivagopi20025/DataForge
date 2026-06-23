from dataforge.domains.healthcare.generators import HealthcareGenerator
from dataforge.domains.healthcare.schemas import HEALTHCARE_SPEC
from dataforge.model import AUDIT_COLUMNS, TIME_HIERARCHY_COLUMNS
from dataforge.validation import schema_report, validate


def test_healthcare_generation_has_expected_tables_and_enterprise_columns():
    data = HealthcareGenerator(120, seed=31, load_type="bulk", scd_type=2).generate()
    assert set(data) == set(HEALTHCARE_SPEC.schemas)
    assert len(data["visits"]) == 120
    assert validate(data, HEALTHCARE_SPEC)["overall_status"] == "PASS"
    assert schema_report(data, HEALTHCARE_SPEC)["overall_status"] == "PASS"
    assert any(row["record_version"] == 2 for row in data["patients"])
    for table, rows in data.items():
        assert set(AUDIT_COLUMNS) <= set(rows[0])
        if table in HEALTHCARE_SPEC.fact_tables:
            assert set(TIME_HIERARCHY_COLUMNS) <= set(rows[0])
