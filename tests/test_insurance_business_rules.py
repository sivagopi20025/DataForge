from dataforge.domains.insurance.generators import InsuranceGenerator
from dataforge.domains.insurance.schemas import INSURANCE_SPEC
from dataforge.validation import validate


def test_insurance_business_rules_pass_for_clean_data():
    data = InsuranceGenerator(100, seed=65).generate()
    checks = validate(data, INSURANCE_SPEC)["checks"]
    names = {check["check"] for check in checks}
    assert "claim_amount_cannot_exceed_coverage" in names
    assert "settlement_amount_cannot_exceed_claim_amount" in names
    assert "cancelled_policies_cannot_generate_premiums" in names
    assert all(check["status"] == "PASS" for check in checks)


def test_insurance_business_rules_catch_claim_and_settlement_overages():
    data = InsuranceGenerator(100, seed=66).generate()
    data["settlements"][0]["settlement_amount"] = "999999999.99"
    settled_claim = next(row for row in data["claims"] if row["claim_id"] == data["settlements"][0]["claim_id"])
    settled_claim["claim_amount"] = "10.00"
    different_claim = next(row for row in data["claims"] if row["claim_id"] != settled_claim["claim_id"])
    different_claim["claim_amount"] = "999999999.99"
    report = validate(data, INSURANCE_SPEC)
    failed = {check["check"] for check in report["checks"] if check["status"] == "FAIL"}
    assert "claim_amount_cannot_exceed_coverage" in failed
    assert "settlement_amount_cannot_exceed_claim_amount" in failed
