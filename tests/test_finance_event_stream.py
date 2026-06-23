import json

from dataforge.cli import main
from dataforge.domains.finance.generators import FinanceGenerator
from dataforge.domains.finance.schemas import FINANCE_SPEC
from dataforge.modes import build_artifacts


def test_finance_event_stream_generates_transaction_card_payment_fraud_events():
    data = FinanceGenerator(120, seed=49, load_type="event_stream").generate()
    artifacts = build_artifacts(data, "event_stream", seed=49, selected_tables={"transactions", "cards", "payments"}, spec=FINANCE_SPEC)
    assert {"events/transaction_event", "events/card_event", "events/payment_event", "events/fraud_event"} <= set(artifacts)
    event = artifacts["events/transaction_event"][0]
    assert event["event_type"] == "TRANSACTION_COMPLETED"
    assert "transaction_id" in json.loads(event["payload"])


def test_finance_event_stream_cli_exports_selected_json(tmp_path):
    assert main(["--domain", "finance", "--records", "30", "--load-type", "event_stream", "--tables", "transactions", "payments", "--output-format", "json", "--output", str(tmp_path), "--dataset-name", "finance-events"]) == 0
    run = next((tmp_path / "finance-events").iterdir())
    assert (run / "events" / "transaction_event.json").exists()
    assert (run / "events" / "payment_event.json").exists()
    assert (run / "events" / "fraud_event.json").exists()
    assert not (run / "events" / "card_event.json").exists()
