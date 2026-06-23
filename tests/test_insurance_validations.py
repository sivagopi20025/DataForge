from dataforge.domains.insurance.generators import InsuranceGenerator
from dataforge.domains.insurance.schemas import INSURANCE_SPEC
from dataforge.validation import validate


def test_insurance_validations_catch_invalid_policy_and_claim_status():
    data = InsuranceGenerator(80, seed=70).generate()
    data["policies"][0]["policy_status"] = "NOT_A_STATUS"
    data["claims"][0]["claim_status"] = "NOT_A_STATUS"
    report = validate(data, INSURANCE_SPEC)
    failed = {check["check"] for check in report["checks"] if check["status"] == "FAIL"}
    assert "policy_status_valid" in failed
    assert "claim_status_valid" in failed


def test_insurance_validations_catch_expired_policy_with_active_claim():
    data = InsuranceGenerator(80, seed=71).generate()
    policy = data["policies"][0]
    policy["policy_status"] = "Expired"
    data["claims"][0]["policy_id"] = policy["policy_id"]
    data["claims"][0]["claim_status"] = "Submitted"
    report = validate(data, INSURANCE_SPEC)
    assert any(check["check"] == "expired_or_cancelled_policies_cannot_accept_active_claims" and check["status"] == "FAIL" for check in report["checks"])
