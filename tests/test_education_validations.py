from dataforge.domains.education.generators import EducationGenerator
from dataforge.domains.education.schemas import EDUCATION_SPEC
from dataforge.validation import validate


def test_education_validations_catch_dates_scores_and_payment_errors():
    data = EducationGenerator(80, seed=95).generate()
    data["students"][0]["expected_graduation_date"] = data["students"][0]["admission_date"]
    data["assignments"][0]["due_date"] = data["assignments"][0]["assigned_date"]
    data["assignment_submissions"][0]["marks_obtained"] = "1000.00"
    data["examination_results"][0]["marks_obtained"] = "1000.00"
    data["attendance"][0]["attendance_percentage"] = "101.00"
    data["fees_payments"][0]["amount_paid"] = "999999.00"
    report = validate(data, EDUCATION_SPEC)
    failed = {check["check"] for check in report["checks"] if check["status"] == "FAIL"}
    assert "student_admission_before_graduation" in failed
    assert "assignment_dates_and_marks_valid" in failed
    assert "examination_results_valid" in failed
    assert "attendance_percentage_between_0_and_100" in failed
    assert "fee_payment_amount_not_above_total" in failed


def test_education_validation_report_uses_standard_contract():
    data = EducationGenerator(40, seed=96).generate()
    report = validate(data, EDUCATION_SPEC, run_id="edu-run-1", load_type="bulk", file_format="json")
    assert set(report) >= {
        "run_id",
        "domain",
        "load_type",
        "format",
        "record_count",
        "quality_score",
        "status",
        "summary",
        "issues",
        "checks",
        "generated_at",
    }
    assert report["domain"] == "education"
    assert report["quality_score"] == 100
    assert report["status"] == "PASS"
