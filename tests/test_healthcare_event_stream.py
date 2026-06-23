import json

from dataforge.cli import main
from dataforge.domains.healthcare.generators import HealthcareGenerator
from dataforge.domains.healthcare.schemas import HEALTHCARE_SPEC
from dataforge.modes import build_artifacts


def test_healthcare_event_stream_generates_visit_claim_payment_events():
    data = HealthcareGenerator(40, seed=38, load_type="event_stream").generate()
    artifacts = build_artifacts(data, "event_stream", seed=38, selected_tables={"visits", "claims", "payments"}, spec=HEALTHCARE_SPEC)
    assert set(artifacts) == {"events/visit_event", "events/claim_event", "events/payment_event"}
    claim_event = artifacts["events/claim_event"][0]
    assert claim_event["event_type"] == "CLAIM_UPDATED"
    assert "claim_id" in json.loads(claim_event["payload"])


def test_healthcare_event_stream_cli_exports_selected_json(tmp_path):
    assert main(["--domain", "healthcare", "--records", "30", "--load-type", "event_stream", "--tables", "claims", "payments", "--output-format", "json", "--output", str(tmp_path), "--dataset-name", "healthcare-events"]) == 0
    run = next((tmp_path / "healthcare-events").iterdir())
    assert (run / "events" / "claim_event.json").exists()
    assert (run / "events" / "payment_event.json").exists()
    assert not (run / "events" / "visit_event.json").exists()
