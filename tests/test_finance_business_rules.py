from dataforge.domains.finance.generators import FinanceGenerator
from dataforge.domains.finance.schemas import FINANCE_SPEC
from dataforge.validation import validate


def test_finance_business_rules_pass_for_clean_data():
    data = FinanceGenerator(100, seed=45).generate()
    checks = validate(data, FINANCE_SPEC)["checks"]
    names = {check["check"] for check in checks}
    assert "savings_balance_non_negative" in names
    assert "payment_amount_cannot_exceed_loan_amount" in names
    assert "closed_or_frozen_accounts_cannot_process_transactions" in names
    assert all(check["status"] == "PASS" for check in checks)


def test_finance_business_rules_catch_negative_savings_and_overpayment():
    data = FinanceGenerator(100, seed=46).generate()
    savings = next(row for row in data["accounts"] if row["account_type"] == "Savings")
    savings["balance"] = "-25.00"
    data["payments"][0]["payment_amount"] = "999999999.99"
    report = validate(data, FINANCE_SPEC)
    failed = {check["check"] for check in report["checks"] if check["status"] == "FAIL"}
    assert "savings_balance_non_negative" in failed
    assert "payment_amount_cannot_exceed_loan_amount" in failed
