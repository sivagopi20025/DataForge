from dataforge.domains.banking.generators import BankingGenerator
from dataforge.domains.banking.schemas import BANKING_SPEC
from dataforge.validation import validate


def test_banking_reconciliation_tags_are_valid_for_clean_data():
    data = BankingGenerator(300, seed=92).generate()
    report = validate(data, BANKING_SPEC)
    assert any(check["check"] == "reconciliation_scenario_valid" and check["status"] == "PASS" for check in report["checks"])
    assert any(row["is_reconciliation_scenario"] for row in data["payments"] + data["transfers"])


def test_banking_reconciliation_validation_catches_invalid_tag():
    data = BankingGenerator(80, seed=93).generate()
    data["payments"][0]["reconciliation_scenario"] = "BAD_RECON"
    report = validate(data, BANKING_SPEC)
    assert any(check["check"] == "reconciliation_scenario_valid" and check["status"] == "FAIL" for check in report["checks"])
