from dataforge.domains.banking.generators import BankingGenerator
from dataforge.domains.banking.schemas import BANKING_SPEC
from dataforge.validation import relationship_report


def test_banking_relationships_have_no_orphans():
    data = BankingGenerator(150, seed=83).generate()
    report = relationship_report(data, BANKING_SPEC)
    assert report["overall_status"] == "PASS"
    assert len(report["relationships"]) == 7


def test_banking_relationship_validation_catches_payment_without_account():
    data = BankingGenerator(50, seed=84).generate()
    data["payments"][0]["account_id"] = 999999999
    report = relationship_report(data, BANKING_SPEC)
    assert report["overall_status"] == "FAIL"
    assert any(item["child_table"] == "payments" and item["child_column"] == "account_id" for item in report["relationships"] if item["status"] == "FAIL")
