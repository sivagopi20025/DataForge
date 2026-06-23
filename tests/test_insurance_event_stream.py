import json

from dataforge.cli import main
from dataforge.domains.insurance.generators import InsuranceGenerator
from dataforge.domains.insurance.schemas import INSURANCE_SPEC
from dataforge.modes import build_artifacts


def test_insurance_event_stream_generates_policy_claim_settlement_premium_fraud_events():
    data = InsuranceGenerator(120, seed=69, load_type="event_stream").generate()
    artifacts = build_artifacts(data, "event_stream", seed=69, selected_tables={"policies", "claims", "settlements", "premiums"}, spec=INSURANCE_SPEC)
    assert {"events/policy_event", "events/claim_event", "events/settlement_event", "events/premium_event", "events/fraud_event"} <= set(artifacts)
    event = artifacts["events/claim_event"][0]
    assert event["event_type"] == "CLAIM_UPDATED"
    assert "claim_id" in json.loads(event["payload"])


def test_insurance_event_stream_cli_exports_selected_json(tmp_path):
    assert main(["--domain", "insurance", "--records", "30", "--load-type", "event_stream", "--tables", "claims", "settlements", "--output-format", "json", "--output", str(tmp_path), "--dataset-name", "insurance-events"]) == 0
    run = next((tmp_path / "insurance-events").iterdir())
    assert (run / "events" / "claim_event.json").exists()
    assert (run / "events" / "settlement_event.json").exists()
    assert (run / "events" / "fraud_event.json").exists()
    assert not (run / "events" / "policy_event.json").exists()
