from dataforge.domains.insurance.generators import InsuranceGenerator
from dataforge.domains.insurance.schemas import INSURANCE_SPEC
from dataforge.validation import relationship_report


def test_insurance_relationships_have_no_orphans():
    data = InsuranceGenerator(150, seed=63).generate()
    report = relationship_report(data, INSURANCE_SPEC)
    assert report["overall_status"] == "PASS"
    assert len(report["relationships"]) == 6


def test_insurance_relationship_validation_catches_claim_without_policy():
    data = InsuranceGenerator(50, seed=64).generate()
    data["claims"][0]["policy_id"] = 999999999
    report = relationship_report(data, INSURANCE_SPEC)
    assert report["overall_status"] == "FAIL"
    assert any(item["child_table"] == "claims" and item["child_column"] == "policy_id" for item in report["relationships"] if item["status"] == "FAIL")
