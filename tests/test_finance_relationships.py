from dataforge.domains.finance.generators import FinanceGenerator
from dataforge.domains.finance.schemas import FINANCE_SPEC
from dataforge.validation import relationship_report


def test_finance_relationships_have_no_orphans():
    data = FinanceGenerator(150, seed=43).generate()
    report = relationship_report(data, FINANCE_SPEC)
    assert report["overall_status"] == "PASS"
    assert len(report["relationships"]) == 13


def test_finance_relationship_validation_catches_transaction_without_account():
    data = FinanceGenerator(50, seed=44).generate()
    data["transactions"][0]["account_id"] = 999999999
    report = relationship_report(data, FINANCE_SPEC)
    assert report["overall_status"] == "FAIL"
    assert any(item["child_table"] == "transactions" and item["child_column"] == "account_id" for item in report["relationships"] if item["status"] == "FAIL")
