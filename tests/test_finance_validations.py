from dataforge.domains.finance.generators import FinanceGenerator
from dataforge.domains.finance.schemas import FINANCE_SPEC
from dataforge.validation import validate


def test_finance_validations_catch_invalid_interest_and_transaction_status():
    data = FinanceGenerator(80, seed=50).generate()
    data["loans"][0]["interest_rate"] = "99.99"
    data["transactions"][0]["transaction_status"] = "NOT_A_STATUS"
    report = validate(data, FINANCE_SPEC)
    failed = {check["check"] for check in report["checks"] if check["status"] == "FAIL"}
    assert "interest_rate_valid" in failed
    assert "transaction_status_valid" in failed


def test_finance_validations_catch_closed_account_processing_transaction():
    data = FinanceGenerator(80, seed=51).generate()
    account = data["accounts"][0]
    account["account_status"] = "Closed"
    data["transactions"][0]["account_id"] = account["account_id"]
    data["transactions"][0]["transaction_status"] = "Success"
    report = validate(data, FINANCE_SPEC)
    assert any(check["check"] == "closed_or_frozen_accounts_cannot_process_transactions" and check["status"] == "FAIL" for check in report["checks"])
