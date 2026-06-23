from dataforge.domains.healthcare.generators import HealthcareGenerator
from dataforge.domains.healthcare.schemas import HEALTHCARE_SPEC
from dataforge.validation import validate


def test_healthcare_business_rules_pass_for_clean_data():
    data = HealthcareGenerator(80, seed=34).generate()
    checks = validate(data, HEALTHCARE_SPEC)["checks"]
    names = {check["check"] for check in checks}
    assert "payment_amount_cannot_exceed_claim_amount" in names
    assert "icd10_code_valid" in names
    assert "cpt_code_valid" in names
    assert all(check["status"] == "PASS" for check in checks)


def test_healthcare_business_rules_catch_invalid_codes_and_payment_overage():
    data = HealthcareGenerator(80, seed=35).generate()
    data["diagnoses"][0]["icd10_code"] = "BAD-ICD"
    data["procedures"][0]["cpt_code"] = "BAD-CPT"
    data["payments"][0]["payment_amount"] = "999999.99"
    report = validate(data, HEALTHCARE_SPEC)
    failed = {check["check"] for check in report["checks"] if check["status"] == "FAIL"}
    assert "icd10_code_valid" in failed
    assert "cpt_code_valid" in failed
    assert "payment_amount_cannot_exceed_claim_amount" in failed
