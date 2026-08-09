from dataforge.domains.education.generators import EducationGenerator
from dataforge.domains.education.schemas import EDUCATION_SPEC
from dataforge.model import AUDIT_COLUMNS, TIME_HIERARCHY_COLUMNS
from dataforge.validation import schema_report, validate


EXPECTED_TABLES = {
    "institutions",
    "campuses",
    "departments",
    "academic_programs",
    "courses",
    "instructors",
    "students",
    "enrollments",
    "class_sections",
    "attendance",
    "assignments",
    "assignment_submissions",
    "examinations",
    "examination_results",
    "fees_payments",
    "academic_standing_events",
}


def test_education_generation_has_expected_tables_and_enterprise_columns():
    data = EducationGenerator(120, seed=91, load_type="bulk", scd_type=2).generate()
    assert set(data) == EXPECTED_TABLES
    assert len(data["enrollments"]) == 120
    assert validate(data, EDUCATION_SPEC)["overall_status"] == "PASS"
    assert schema_report(data, EDUCATION_SPEC)["overall_status"] == "PASS"
    assert any(row["record_version"] == 2 for row in data["students"])
    for table, rows in data.items():
        assert set(AUDIT_COLUMNS) <= set(rows[0])
        if table in EDUCATION_SPEC.fact_tables:
            assert set(TIME_HIERARCHY_COLUMNS) <= set(rows[0])


def test_education_temporal_scores_and_payments_are_business_consistent():
    data = EducationGenerator(100, seed=92).generate()
    assert all(row["admission_date"] < row["expected_graduation_date"] for row in data["students"])
    assert all(row["assigned_date"] < row["due_date"] for row in data["assignments"])
    assert all(0 <= float(row["attendance_percentage"]) <= 100 for row in data["attendance"])
    assert all(float(row["amount_paid"]) <= float(row["total_fee"]) for row in data["fees_payments"])
    assert all(float(row["marks_obtained"]) <= 100 for row in data["assignment_submissions"])
    assert all(float(row["marks_obtained"]) <= 100 for row in data["examination_results"])
    assert all(0 <= float(row["gpa"]) <= 4 for row in data["academic_standing_events"])
