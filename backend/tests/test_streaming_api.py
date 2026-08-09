from __future__ import annotations

import hashlib
import hmac
import json

import pytest

from backend.app.core.config import get_settings
from backend.app.models import StreamSession
from backend.app.services.streaming import STREAM_EVENT_TYPES, STREAM_FAILURE_TYPES
from backend.app.services.streaming import validate_webhook_url


MVP_DOMAINS = ("manufacturing", "telecommunications", "ecommerce", "logistics", "banking")


def _start_stream(client, domain: str, *, seed: int = 42, failure_injections: dict | None = None):
    response = client.post(
        "/api/v1/streams/start",
        json={
            "domain": domain,
            "event_types": list(STREAM_EVENT_TYPES[domain])[:2],
            "events_per_second": 1,
            "duration_minutes": 1,
            "format": "json",
            "seed": seed,
            "failure_injections": failure_injections or {},
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_stream_session_creation_status_events_replay_and_sse(client):
    started = _start_stream(client, "logistics", seed=11)

    assert started["stream_id"]
    assert started["status"] == "queued"
    assert started["domain"] == "logistics"
    assert started["events_per_second"] == 1
    assert started["stream_token"].startswith("dfst_")
    assert "/api/v1/streams/" in started["pull_url"]
    assert started["stream_token"] not in started["pull_url"]
    assert "stream_token=" not in started["sse_url"]
    assert "stream_token=" not in started["latest_url"]
    assert set(started["event_type_urls"]) == set(STREAM_EVENT_TYPES["logistics"])

    status = client.get(f"/api/v1/streams/{started['stream_id']}").json()
    assert status["status"] == "completed"
    assert status["events_generated"] == 60
    assert status["events_failed"] == 0
    assert status["failure_summary"] == {}

    events = client.get(f"/api/v1/streams/{started['stream_id']}/events", params={"limit": 5}).json()
    assert events["total"] == 60
    assert len(events["events"]) == 5
    first = events["events"][0]
    assert {
        "event_id",
        "event_type",
        "domain",
        "event_time",
        "ingestion_time",
        "sequence_number",
        "correlation_id",
        "payload",
        "injected_issues",
    } <= set(first)

    replay = client.post(f"/api/v1/streams/{started['stream_id']}/replay").json()
    assert replay["events"][0]["event_id"] == first["event_id"]

    sse = client.get(f"/api/v1/streams/{started['stream_id']}/sse")
    assert sse.status_code == 200
    assert "event: data" in sse.text
    assert "event: done" in sse.text


def test_stream_events_can_be_pulled_by_stream_token(client):
    started = _start_stream(client, "logistics", seed=12)
    stream_id = started["stream_id"]

    response = client.get(
        f"/api/v1/streams/{stream_id}/events",
        headers={"Authorization": f"Bearer {started['stream_token']}"},
        params={"limit": 3},
    )

    assert response.status_code == 200
    assert len(response.json()["events"]) == 3


def test_stream_token_is_scoped_to_one_stream(client):
    first = _start_stream(client, "logistics", seed=13)
    second = _start_stream(client, "banking", seed=14)

    response = client.get(f"/api/v1/streams/{second['stream_id']}/events", headers={"Authorization": f"Bearer {first['stream_token']}"})

    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHORIZED"


def test_stream_event_type_endpoint_filters_correctly(client):
    started = _start_stream(client, "logistics", seed=15)
    stream_id = started["stream_id"]
    event_type = list(STREAM_EVENT_TYPES["logistics"])[0]

    response = client.get(
        f"/api/v1/streams/{stream_id}/events/{event_type}",
        headers={"Authorization": f"Bearer {started['stream_token']}"},
        params={"limit": 20},
    )
    events = response.json()["events"]

    assert response.status_code == 200
    assert events
    assert {event["event_type"] for event in events} == {event_type}


def test_stream_after_sequence_pagination(client):
    started = _start_stream(client, "logistics", seed=16)

    response = client.get(
        f"/api/v1/streams/{started['stream_id']}/events",
        headers={"Authorization": f"Bearer {started['stream_token']}"},
        params={"after_sequence": 10, "limit": 5},
    )
    events = response.json()["events"]

    assert response.status_code == 200
    assert len(events) == 5
    assert all(event["sequence_number"] > 10 for event in events)


def test_stream_latest_endpoint_returns_last_event(client):
    started = _start_stream(client, "banking", seed=17)

    latest = client.get(f"/api/v1/streams/{started['stream_id']}/events/latest", headers={"Authorization": f"Bearer {started['stream_token']}"})

    assert latest.status_code == 200
    assert latest.json()["event"]["sequence_number"] == 60


def test_stream_sse_endpoint_filters_by_event_type(client):
    started = _start_stream(client, "logistics", seed=18)
    event_type = list(STREAM_EVENT_TYPES["logistics"])[0]

    response = client.get(f"/api/v1/streams/{started['stream_id']}/sse/{event_type}", headers={"Authorization": f"Bearer {started['stream_token']}"})

    assert response.status_code == 200
    assert "event: data" in response.text
    assert event_type in response.text
    other_event_types = set(STREAM_EVENT_TYPES["logistics"]) - {event_type}
    assert not any(other in response.text for other in other_event_types)


def test_stream_webhook_push_signs_payload_and_stores_summary(client, monkeypatch):
    calls = []

    class FakeWebhookResponse:
        status = 204

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    class FakeWebhookOpener:
        def open(self, req, timeout):
            calls.append(req)
            return FakeWebhookResponse()

    monkeypatch.setattr("backend.app.services.streaming._webhook_opener", lambda: FakeWebhookOpener())
    secret = "demo-webhook-secret"
    started = client.post(
        "/api/v1/streams/start",
        json={
            "domain": "logistics",
            "event_types": ["shipment_created_event"],
            "events_per_second": 1,
            "duration_minutes": 1,
            "format": "json",
            "seed": 19,
            "webhook_url": "https://example.com/dataforge-webhook",
            "webhook_secret": secret,
        },
    )
    assert started.status_code == 200, started.text

    assert len(calls) == 60
    first = calls[0]
    body = first.data.decode("utf-8")
    expected_signature = hmac.new(secret.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).hexdigest()
    assert first.headers["X-dataforge-signature"] == f"sha256={expected_signature}"
    assert json.loads(body)["event"]["event_type"] == "shipment_created_event"

    status = client.get(f"/api/v1/streams/{started.json()['stream_id']}")
    delivery = status.json()["webhook_delivery_summary"]
    assert delivery["delivered"] == 60
    assert delivery["last_status"] == "delivered"
    assert delivery["last_response_code"] == 204
    assert delivery["last_error"] is None
    with client.app.state.SessionLocal() as db:
        session = db.get(StreamSession, started.json()["stream_id"])
        assert session is not None
        assert not hasattr(session, "webhook_secret")
        assert session.webhook_secret_hash


@pytest.mark.parametrize(
    "webhook_url",
    [
        "http://example.com/dataforge-webhook",
        "https://localhost/dataforge-webhook",
        "https://127.0.0.1/dataforge-webhook",
        "https://10.0.0.5/dataforge-webhook",
        "https://169.254.169.254/latest/meta-data",
    ],
)
def test_stream_webhook_rejects_unsafe_targets(client, webhook_url):
    response = client.post(
        "/api/v1/streams/start",
        json={
            "domain": "logistics",
            "event_types": ["shipment_created_event"],
            "events_per_second": 1,
            "duration_minutes": 1,
            "format": "json",
            "seed": 19,
            "webhook_url": webhook_url,
            "webhook_secret": "secret",
        },
    )

    assert response.status_code in {400, 422}


def test_webhook_production_requires_allowlisted_domain(monkeypatch):
    monkeypatch.setattr("backend.app.services.streaming.socket.getaddrinfo", lambda *args, **kwargs: [(None, None, None, None, ("93.184.216.34", 443))])
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATAFORGE_API_KEY", "secret-test-key")
    monkeypatch.setenv("CORS_ORIGINS", "https://app.example.com")
    monkeypatch.delenv("WEBHOOK_ALLOWED_DOMAINS", raising=False)
    get_settings.cache_clear()
    with pytest.raises(ValueError, match="WEBHOOK_ALLOWED_DOMAINS"):
        validate_webhook_url("https://hooks.example.com/dataforge")

    monkeypatch.setenv("WEBHOOK_ALLOWED_DOMAINS", "hooks.example.com")
    get_settings.cache_clear()
    assert validate_webhook_url("https://hooks.example.com/dataforge") == "https://hooks.example.com/dataforge"
    with pytest.raises(ValueError, match="not in WEBHOOK_ALLOWED_DOMAINS"):
        validate_webhook_url("https://other.example.com/dataforge")
    get_settings.cache_clear()


def test_query_stream_token_is_rejected_in_production(client, monkeypatch):
    started = _start_stream(client, "logistics", seed=44)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATAFORGE_API_KEY", "secret-test-key")
    monkeypatch.setenv("CORS_ORIGINS", "https://app.example.com")
    get_settings.cache_clear()

    response = client.get(
        f"/api/v1/streams/{started['stream_id']}/events",
        params={"stream_token": started["stream_token"]},
    )

    assert response.status_code == 401
    assert "Query-string stream tokens are disabled" in response.json()["error"]
    get_settings.cache_clear()


@pytest.mark.parametrize("domain", MVP_DOMAINS)
def test_stream_event_generation_for_mvp_domains(client, domain):
    started = _start_stream(client, domain, seed=22)
    events = client.get(f"/api/v1/streams/{started['stream_id']}/events", params={"limit": 20}).json()["events"]

    assert events
    assert {event["domain"] for event in events} == {domain}
    assert {event["event_type"] for event in events} <= set(STREAM_EVENT_TYPES[domain])
    assert all(event["payload"] for event in events)


def test_manufacturing_event_payloads_are_event_type_specific(client):
    started = client.post(
        "/api/v1/streams/start",
        json={
            "domain": "manufacturing",
            "event_types": list(STREAM_EVENT_TYPES["manufacturing"]),
            "events_per_second": 1,
            "duration_minutes": 1,
            "format": "json",
            "seed": 23,
        },
    ).json()
    events = client.get(
        f"/api/v1/streams/{started['stream_id']}/events",
        headers={"Authorization": f"Bearer {started['stream_token']}"},
        params={"limit": 10},
    ).json()["events"]
    payload_by_type = {event["event_type"]: event["payload"] for event in events}

    assert "temperature_celsius" in payload_by_type["machine_sensor"]
    assert "units_produced" in payload_by_type["production_event"]
    assert "defect_count" in payload_by_type["quality_event"]
    assert "recommended_action" in payload_by_type["maintenance_alert"]
    assert "downtime_reason" in payload_by_type["downtime_event"]


def test_stream_seed_behavior_is_deterministic_for_event_identity_and_payload(client):
    first = _start_stream(client, "banking", seed=99)
    second = _start_stream(client, "banking", seed=99)

    first_events = client.get(f"/api/v1/streams/{first['stream_id']}/events", params={"limit": 5}).json()["events"]
    second_events = client.get(f"/api/v1/streams/{second['stream_id']}/events", params={"limit": 5}).json()["events"]

    comparable_first = [(event["event_id"], event["event_type"], event["sequence_number"], event["payload"]) for event in first_events]
    comparable_second = [(event["event_id"], event["event_type"], event["sequence_number"], event["payload"]) for event in second_events]
    assert comparable_first == comparable_second


@pytest.mark.parametrize("failure_type", sorted(STREAM_FAILURE_TYPES))
def test_stream_failure_injections_are_detected_and_reported(client, failure_type):
    started = _start_stream(client, "manufacturing", seed=7, failure_injections={failure_type: True})
    stream_id = started["stream_id"]

    status = client.get(f"/api/v1/streams/{stream_id}").json()
    assert status["status"] == "completed"
    assert status["failure_summary"][failure_type] >= 1

    validation = client.get(f"/api/v1/streams/{stream_id}/validation").json()
    matching = [check for check in validation["checks"] if check["name"] == f"{failure_type} detected"]
    assert matching
    assert matching[0]["status"] == "FAIL"
    assert validation["quality_score"] < 100

    events = client.get(f"/api/v1/streams/{stream_id}/events", params={"limit": 1000}).json()["events"]
    assert any(failure_type in event["injected_issues"] for event in events)


def test_stream_stop_endpoint_returns_terminal_status(client):
    started = _start_stream(client, "telecommunications", seed=33)

    stopped = client.post(f"/api/v1/streams/{started['stream_id']}/stop").json()

    assert stopped["stream_id"] == started["stream_id"]
    assert stopped["status"] in {"completed", "stopped"}


def test_stream_start_rejects_non_mvp_domain_and_invalid_event_type(client):
    unsupported = client.post(
        "/api/v1/streams/start",
        json={
            "domain": "retail",
            "event_types": ["sale_event"],
            "events_per_second": 1,
            "duration_minutes": 1,
            "format": "json",
            "seed": 1,
        },
    )
    assert unsupported.status_code == 400

    invalid_event = client.post(
        "/api/v1/streams/start",
        json={
            "domain": "logistics",
            "event_types": ["not_real"],
            "events_per_second": 1,
            "duration_minutes": 1,
            "format": "json",
            "seed": 1,
        },
    )
    assert invalid_event.status_code == 400
