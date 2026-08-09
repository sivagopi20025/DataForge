from dataforge.domains.education.generators import EducationGenerator
from dataforge.domains.education.schemas import EDUCATION_SPEC
from dataforge.validation import relationship_report


def test_education_relationships_have_no_orphans():
    data = EducationGenerator(150, seed=93).generate()
    report = relationship_report(data, EDUCATION_SPEC)
    assert report["overall_status"] == "PASS"
    assert len(report["relationships"]) == 20


def test_education_relationship_validation_catches_orphan_enrollment_student():
    data = EducationGenerator(80, seed=94).generate()
    data["enrollments"][0]["student_id"] = 999999999
    report = relationship_report(data, EDUCATION_SPEC)
    assert report["overall_status"] == "FAIL"
    assert any(
        item["child_table"] == "enrollments" and item["child_column"] == "student_id"
        for item in report["relationships"]
        if item["status"] == "FAIL"
    )
