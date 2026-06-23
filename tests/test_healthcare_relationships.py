from dataforge.domains.healthcare.generators import HealthcareGenerator
from dataforge.domains.healthcare.schemas import HEALTHCARE_SPEC
from dataforge.validation import relationship_report


def test_healthcare_relationships_have_no_orphans():
    data = HealthcareGenerator(150, seed=32).generate()
    report = relationship_report(data, HEALTHCARE_SPEC)
    assert report["overall_status"] == "PASS"
    assert len(report["relationships"]) == 8


def test_healthcare_relationship_validation_catches_claim_without_visit():
    data = HealthcareGenerator(50, seed=33).generate()
    data["claims"][0]["visit_id"] = 999999999
    report = relationship_report(data, HEALTHCARE_SPEC)
    assert report["overall_status"] == "FAIL"
    assert any(item["child_table"] == "claims" and item["child_column"] == "visit_id" for item in report["relationships"] if item["status"] == "FAIL")
