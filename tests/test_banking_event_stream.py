import json

from dataforge.cli import main
from dataforge.domains.banking.generators import BankingGenerator
from dataforge.domains.banking.schemas import BANKING_SPEC
from dataforge.modes import build_artifacts


def test_banking_event_stream_generates_payment_transfer_treasury_fraud_events():
    data = BankingGenerator(120, seed=89, load_type="event_stream").generate()
    artifacts = build_artifacts(
        data,
        "event_stream",
        seed=89,
        selected_tables={"payments", "transfers", "treasury_transactions"},
        spec=BANKING_SPEC,
    )
    assert {"events/payment_event", "events/transfer_event", "events/treasury_event", "events/fraud_event"} <= set(artifacts)
    event = artifacts["events/payment_event"][0]
    assert event["event_type"] == "PAYMENT_COMPLETED"
    assert "payment_id" in json.loads(event["payload"])


def test_banking_event_stream_cli_exports_selected_json(tmp_path):
    assert main(["--domain", "banking", "--records", "30", "--load-type", "event_stream", "--tables", "payments", "transfers", "--output-format", "json", "--output", str(tmp_path), "--dataset-name", "banking-events"]) == 0
    run = next((tmp_path / "banking-events").iterdir())
    assert (run / "events" / "payment_event.json").exists()
    assert (run / "events" / "transfer_event.json").exists()
    assert (run / "events" / "fraud_event.json").exists()
    assert not (run / "events" / "treasury_event.json").exists()
