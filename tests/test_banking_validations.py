from dataforge.domains.banking.generators import BankingGenerator
from dataforge.domains.banking.schemas import BANKING_SPEC
from dataforge.validation import validate


def test_banking_validations_catch_invalid_payment_and_transfer_status():
    data = BankingGenerator(80, seed=90).generate()
    data["payments"][0]["payment_status"] = "NOT_A_STATUS"
    data["transfers"][0]["transfer_status"] = "NOT_A_STATUS"
    report = validate(data, BANKING_SPEC)
    failed = {check["check"] for check in report["checks"] if check["status"] == "FAIL"}
    assert "payment_status_valid" in failed
    assert "transfer_status_valid" in failed


def test_banking_validations_catch_closed_account_payment_and_currency_mismatch():
    data = BankingGenerator(80, seed=91).generate()
    account = data["deposit_accounts"][0]
    account["account_status"] = "Closed"
    data["payments"][0]["account_id"] = account["account_id"]
    data["payments"][0]["payment_status"] = "Completed"
    data["payments"][0]["currency"] = "EUR" if account["currency"] != "EUR" else "USD"
    report = validate(data, BANKING_SPEC)
    failed = {check["check"] for check in report["checks"] if check["status"] == "FAIL"}
    assert "closed_accounts_cannot_process_payments" in failed
    assert "payment_currency_valid" in failed
