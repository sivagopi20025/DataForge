import json

from dataforge.domains.finance.generators import FinanceGenerator
from dataforge.domains.finance.schemas import FINANCE_SPEC
from dataforge.modes import build_artifacts


def test_finance_cdc_generates_insert_update_delete_for_transactions():
    data = FinanceGenerator(50, seed=47, load_type="cdc").generate()
    artifacts = build_artifacts(data, "cdc", seed=47, selected_tables={"transactions"}, spec=FINANCE_SPEC)
    assert set(artifacts) == {"cdc/transactions_cdc"}
    event_types = {row["event_type"] for row in artifacts["cdc/transactions_cdc"]}
    assert {"INSERT", "UPDATE", "DELETE"} <= event_types
    payload = next(row["after_value"] or row["before_value"] for row in artifacts["cdc/transactions_cdc"])
    assert "transaction_id" in json.loads(payload)


def test_finance_cdc_supports_accounts_transactions_cards_loans_payments():
    data = FinanceGenerator(20, seed=48, load_type="cdc").generate()
    artifacts = build_artifacts(data, "cdc", seed=48, selected_tables={"accounts", "transactions", "cards", "loans", "payments"}, spec=FINANCE_SPEC)
    assert set(artifacts) == {"cdc/accounts_cdc", "cdc/transactions_cdc", "cdc/cards_cdc", "cdc/loans_cdc", "cdc/payments_cdc"}
