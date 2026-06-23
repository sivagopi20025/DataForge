import json

from dataforge.domains.banking.generators import BankingGenerator
from dataforge.domains.banking.schemas import BANKING_SPEC
from dataforge.modes import build_artifacts


def test_banking_cdc_generates_insert_update_delete_for_payments():
    data = BankingGenerator(50, seed=87, load_type="cdc").generate()
    artifacts = build_artifacts(data, "cdc", seed=87, selected_tables={"payments"}, spec=BANKING_SPEC)
    assert set(artifacts) == {"cdc/payments_cdc"}
    event_types = {row["event_type"] for row in artifacts["cdc/payments_cdc"]}
    assert {"INSERT", "UPDATE", "DELETE"} <= event_types
    payload = next(row["after_value"] or row["before_value"] for row in artifacts["cdc/payments_cdc"])
    assert "payment_id" in json.loads(payload)


def test_banking_cdc_supports_accounts_payments_transfers_treasury():
    data = BankingGenerator(20, seed=88, load_type="cdc").generate()
    artifacts = build_artifacts(
        data,
        "cdc",
        seed=88,
        selected_tables={"deposit_accounts", "payments", "transfers", "treasury_positions", "treasury_transactions"},
        spec=BANKING_SPEC,
    )
    assert set(artifacts) == {
        "cdc/deposit_accounts_cdc",
        "cdc/payments_cdc",
        "cdc/transfers_cdc",
        "cdc/treasury_positions_cdc",
        "cdc/treasury_transactions_cdc",
    }
