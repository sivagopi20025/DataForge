from dataforge.domains.banking.generators import BankingGenerator
from dataforge.domains.banking.schemas import BANKING_SPEC
from dataforge.validation import validate


def test_banking_business_rules_pass_for_clean_data():
    data = BankingGenerator(100, seed=85).generate()
    checks = validate(data, BANKING_SPEC)["checks"]
    names = {check["check"] for check in checks}
    assert "transfer_amount_positive" in names
    assert "closed_accounts_cannot_process_payments" in names
    assert "treasury_position_non_negative" in names
    assert all(check["status"] == "PASS" for check in checks)


def test_banking_business_rules_catch_negative_transfer_and_treasury_position():
    data = BankingGenerator(100, seed=86).generate()
    data["transfers"][0]["transfer_amount"] = "-10.00"
    data["treasury_positions"][0]["cash_position"] = "-100.00"
    report = validate(data, BANKING_SPEC)
    failed = {check["check"] for check in report["checks"] if check["status"] == "FAIL"}
    assert "transfer_amount_positive" in failed
    assert "treasury_position_non_negative" in failed
