from __future__ import annotations

import json
import hashlib
import hmac
import ipaddress
import random
import secrets
import socket
import threading
import uuid
from collections import Counter
from collections.abc import Callable, Iterable
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib import request as urlrequest
from urllib.error import URLError
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from backend.app.db.session import SessionLocal
from backend.app.core.config import get_settings
from backend.app.repositories import StreamSessionRepository
from backend.app.schemas.api import StreamStartRequest
from dataforge.scenarios.models import ScenarioRunConfig
from dataforge.scenarios.registry import get_scenario
from dataforge.scenarios.validator import SEVERITY_RATES
from dataforge.scenarios.validators import scenario_outcome_from_validations, validate_scenario_events

STREAM_EVENT_TYPES: dict[str, tuple[str, ...]] = {
    "manufacturing": ("machine_sensor", "production_event", "quality_event", "maintenance_alert", "downtime_event"),
    "telecommunications": ("call_detail_event", "sms_event", "data_session_event", "tower_outage_event", "billing_usage_event"),
    "ecommerce": ("product_view_event", "cart_update_event", "order_created_event", "payment_event", "shipment_event", "return_event"),
    "logistics": ("shipment_created_event", "tracking_event", "gps_event", "delivery_status_event", "delay_alert_event"),
    "banking": ("account_activity_event", "transaction_event", "transfer_event", "fraud_alert_event", "ledger_event"),
}

STREAM_FAILURE_TYPES = {
    "late_events",
    "duplicate_events",
    "out_of_order_events",
    "missing_events",
    "schema_drift",
    "malformed_json",
    "future_timestamp",
    "clock_skew",
    "burst_traffic",
}

STREAM_VALIDATION_NAMES = {
    "late_events": "late_events detected",
    "duplicate_events": "duplicate_events detected",
    "out_of_order_events": "out_of_order_events detected",
    "missing_events": "missing_events detected",
    "schema_drift": "schema_drift detected",
    "malformed_json": "malformed_json detected",
    "future_timestamp": "future_timestamp detected",
    "clock_skew": "clock_skew detected",
    "burst_traffic": "burst_traffic detected",
}

MAX_STREAM_EVENTS = 10_000
STREAM_TOKEN_TTL_HOURS = 24
WEBHOOK_MAX_RETRIES = 3
CLOUD_METADATA_IPS = {
    ipaddress.ip_address("169.254.169.254"),
    ipaddress.ip_address("100.100.100.200"),
}
_WEBHOOK_SECRET_CACHE: dict[str, str] = {}
_WEBHOOK_SECRET_LOCK = threading.Lock()


class StreamSessionService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.sessions = StreamSessionRepository(db)

    def start(self, request: StreamStartRequest) -> dict[str, Any]:
        _validate_stream_request(request)
        webhook_url = validate_webhook_url(str(request.webhook_url)) if request.webhook_url else None
        started_at = datetime.now(timezone.utc)
        estimated_end_at = started_at + timedelta(minutes=request.duration_minutes)
        stream_token = generate_stream_token()
        token_expires_at = started_at + timedelta(hours=STREAM_TOKEN_TTL_HOURS)
        session = self.sessions.create(
            domain=request.domain,
            event_types=request.event_types,
            events_per_second=request.events_per_second,
            duration_minutes=request.duration_minutes,
            file_format=request.format,
            seed=request.seed,
            failure_injections=request.failure_injections,
            stream_token_hash=hash_stream_token(stream_token),
            stream_token_expires_at=token_expires_at,
            webhook_url=webhook_url,
            webhook_secret_hash=hash_stream_token(request.webhook_secret) if request.webhook_secret else None,
            started_at=started_at,
            estimated_end_at=estimated_end_at,
        )
        if request.webhook_secret:
            store_ephemeral_webhook_secret(session.id, request.webhook_secret)
        if request.scenario_id:
            session.webhook_delivery_summary = json.dumps({
                "scenario_metadata": {
                    "scenario_id": request.scenario_id,
                    "scenario_run_config": request.scenario_run_config or {},
                    "scenario_definition": request.scenario_definition or {},
                }
            })
        self.db.commit()
        return {
            "stream_id": session.id,
            "status": session.status,
            "domain": session.domain,
            "started_at": session.started_at,
            "estimated_end_at": session.estimated_end_at,
            "events_per_second": session.events_per_second,
            "duration_minutes": session.duration_minutes,
            "stream_token": stream_token,
            "stream_token_expires_at": token_expires_at,
        }

    def status(self, stream_id: str) -> dict[str, Any]:
        session = self.sessions.get(stream_id)
        if not session:
            raise ValueError(f"Stream session not found: {stream_id}")
        return stream_status_payload(session)

    def events(
        self,
        stream_id: str,
        *,
        limit: int = 100,
        offset: int = 0,
        after_sequence: int | None = None,
        event_type: str | None = None,
    ) -> dict[str, Any]:
        session = self.sessions.get(stream_id)
        if not session:
            raise ValueError(f"Stream session not found: {stream_id}")
        rows = self.sessions.find_events(stream_id, limit=limit, offset=offset, after_sequence=after_sequence, event_type=event_type)
        return {
            "stream_id": stream_id,
            "total": self.sessions.count_events(stream_id, after_sequence=after_sequence, event_type=event_type),
            "events": [stream_event_payload(row) for row in rows],
        }

    def latest_event(self, stream_id: str, *, event_type: str | None = None) -> dict[str, Any]:
        session = self.sessions.get(stream_id)
        if not session:
            raise ValueError(f"Stream session not found: {stream_id}")
        row = self.sessions.latest_event(stream_id, event_type=event_type)
        if not row:
            raise ValueError(f"No events found for stream: {stream_id}")
        return {"stream_id": stream_id, "event": stream_event_payload(row)}

    def authorize_token(self, stream_id: str, token: str) -> None:
        session = self.sessions.get(stream_id)
        if not session:
            raise ValueError(f"Stream session not found: {stream_id}")
        if not session.stream_token_hash or not hmac.compare_digest(session.stream_token_hash, hash_stream_token(token)):
            raise PermissionError("Invalid stream token")
        expires_at = _aware_utc(session.stream_token_expires_at)
        if expires_at and expires_at < datetime.now(timezone.utc):
            raise PermissionError("Stream token expired")

    def stop(self, stream_id: str) -> dict[str, Any]:
        session = self.sessions.get(stream_id)
        if not session:
            raise ValueError(f"Stream session not found: {stream_id}")
        if session.status in {"queued", "running"}:
            self.sessions.mark_stopped(session, completed_at=datetime.now(timezone.utc))
            self.db.commit()
        return stream_status_payload(session)

    def replay(self, stream_id: str) -> dict[str, Any]:
        session = self.sessions.get(stream_id)
        if not session:
            raise ValueError(f"Stream session not found: {stream_id}")
        if session.status not in {"completed", "stopped"}:
            raise ValueError(f"Stream session is not replayable while status is {session.status}")
        return self.events(stream_id, limit=100, offset=0)


def run_stream_session(stream_id: str, session_factory: Callable[[], Session] = SessionLocal) -> None:
    db = session_factory()
    repo = StreamSessionRepository(db)
    try:
        session = repo.get(stream_id)
        if not session or session.status != "queued":
            return
        repo.mark_running(session)
        db.commit()
        scenario_metadata = json.loads(session.webhook_delivery_summary or "{}").get("scenario_metadata")
        events, failure_summary = generate_stream_events(
            domain=session.domain,
            event_types=json.loads(session.event_types),
            events_per_second=session.events_per_second,
            duration_minutes=session.duration_minutes,
            seed=session.seed,
            failure_injections=json.loads(session.failure_injections),
            started_at=session.started_at,
            scenario_metadata=scenario_metadata,
        )
        failed = 0
        webhook_summary: Counter[str] = Counter()
        webhook_delivery_detail: dict[str, Any] = {}
        webhook_secret = pop_ephemeral_webhook_secret(stream_id)
        for event in events:
            raw_event = None
            is_malformed = "malformed_json" in event["injected_issues"]
            if is_malformed:
                raw_event = json.dumps(serialize_stream_event(event), default=str)[:-1]
                failed += 1
            repo.add_event(stream_id=stream_id, event=event, raw_event=raw_event, is_malformed=is_malformed)
            if session.webhook_url:
                result = deliver_webhook_event(session.webhook_url, webhook_secret, serialize_stream_event(event))
                webhook_summary[result["status"]] += 1
                webhook_delivery_detail = {
                    "last_status": result["status"],
                    "last_response_code": result["last_response_code"],
                    "last_error": result["last_error"],
                    "last_attempts": result["attempts"],
                }
        session = repo.get(stream_id)
        if session and session.status == "running":
            repo.update_counts(session, generated=len(events), failed=failed)
            if session.webhook_url:
                repo.update_webhook_summary(session, {**dict(webhook_summary), **webhook_delivery_detail})
            repo.mark_completed(session, completed_at=datetime.now(timezone.utc), failure_summary=failure_summary)
            db.commit()
    except Exception:
        db.rollback()
        session = repo.get(stream_id)
        if session:
            pop_ephemeral_webhook_secret(stream_id)
            repo.mark_failed(session, completed_at=datetime.now(timezone.utc), failure_summary={"stream_failure": 1})
            db.commit()
        raise
    finally:
        db.close()


def generate_stream_events(
    *,
    domain: str,
    event_types: list[str],
    events_per_second: int,
    duration_minutes: int,
    seed: int,
    failure_injections: dict[str, Any],
    started_at: datetime,
    scenario_metadata: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    rng = random.Random(seed)
    total_events = min(events_per_second * duration_minutes * 60, MAX_STREAM_EVENTS)
    active_failures = _active_failures(failure_injections)
    skipped_sequences = _failure_indexes(total_events, active_failures.get("missing_events", 0), rng)
    duplicate_indexes = _failure_indexes(total_events, active_failures.get("duplicate_events", 0), rng)
    out_of_order_indexes = _failure_indexes(total_events, active_failures.get("out_of_order_events", 0), rng)
    burst_indexes = _failure_indexes(total_events, active_failures.get("burst_traffic", 0), rng)
    failure_summary: Counter[str] = Counter()
    events: list[dict[str, Any]] = []
    pending_missing_events = 0
    scenario_id = (scenario_metadata or {}).get("scenario_id")
    scenario_config = (scenario_metadata or {}).get("scenario_run_config") or {}
    scenario_severity = scenario_config.get("severity") or "medium"
    scenario_rate = SEVERITY_RATES.get(scenario_severity, 0.03)
    scenario_indexes = _failure_indexes(total_events, scenario_rate, rng) if scenario_id == "telecom_tower_congestion" and domain == "telecommunications" else set()

    for sequence in range(1, total_events + 1):
        if sequence in skipped_sequences:
            failure_summary["missing_events"] += 1
            pending_missing_events += 1
            continue
        event_type = event_types[(sequence - 1) % len(event_types)]
        event_time = started_at + timedelta(seconds=sequence / max(events_per_second, 1))
        ingestion_time = event_time + timedelta(milliseconds=rng.randrange(10, 900))
        injected = []
        missing_gap_count = pending_missing_events
        if pending_missing_events:
            injected.append("missing_events")
            pending_missing_events = 0

        for failure in ("late_events", "schema_drift", "malformed_json", "future_timestamp", "clock_skew"):
            if _should_inject(sequence, total_events, active_failures.get(failure, 0), rng):
                injected.append(failure)
                failure_summary[failure] += 1

        if "late_events" in injected:
            event_time -= timedelta(minutes=15)
        if "future_timestamp" in injected:
            event_time += timedelta(days=1)
        if "clock_skew" in injected:
            ingestion_time = event_time - timedelta(seconds=30)
        if sequence in out_of_order_indexes:
            injected.append("out_of_order_events")
            failure_summary["out_of_order_events"] += 1
            event_time -= timedelta(seconds=sequence + 5)
        if sequence in burst_indexes:
            injected.append("burst_traffic")
            failure_summary["burst_traffic"] += 1
        scenario_congestion = sequence in scenario_indexes
        if scenario_congestion:
            injected.append("tower_congestion")
            failure_summary["tower_congestion"] += 1
            if event_type == "data_session_event":
                failure_summary["failed_session_rate"] += 1
            if event_type == "call_detail_event":
                failure_summary["dropped_call_rate"] += 1
            if "delayed_network_events" in scenario_config.get("variation_ids", []):
                injected.append("out_of_order_events")
                failure_summary["out_of_order_events"] += 1
                event_time -= timedelta(seconds=sequence + 11)

        event = {
            "event_id": _event_id(domain, seed, sequence, event_type),
            "event_type": event_type,
            "domain": domain,
            "event_time": event_time,
            "ingestion_time": ingestion_time,
            "sequence_number": sequence,
            "correlation_id": f"{domain[:4]}-{seed}-{sequence // 5:06d}",
            "payload": _payload_for(domain, event_type, sequence, rng),
            "injected_issues": injected,
        }
        if scenario_congestion:
            _apply_telecom_congestion_payload(event, sequence)
        if missing_gap_count:
            event["payload"]["missing_event_gap_count"] = missing_gap_count
        if "schema_drift" in injected:
            event["payload"]["unexpected_field_v2"] = f"drift-{sequence}"
        events.append(event)
        if sequence in duplicate_indexes:
            duplicate = {**event, "event_id": f"{event['event_id']}-dup", "injected_issues": [*event["injected_issues"], "duplicate_events"]}
            failure_summary["duplicate_events"] += 1
            events.append(duplicate)

    return events, dict(failure_summary)


def _apply_telecom_congestion_payload(event: dict[str, Any], sequence: int) -> None:
    payload = event["payload"]
    tower_id = payload.get("tower_id", f"TOWER{sequence % 800:05d}")
    payload["tower_id"] = tower_id
    payload["tower_load_pct"] = 98
    payload["congestion_status"] = "congested"
    payload["support_ticket_correlation_id"] = event["correlation_id"]
    if event["event_type"] == "data_session_event":
        payload["session_status"] = "Failed"
        payload["failure_reason"] = "tower_congestion"
    elif event["event_type"] == "call_detail_event":
        payload["call_status"] = "Dropped"
        payload["drop_reason"] = "tower_congestion"
    elif event["event_type"] == "tower_outage_event":
        payload["event_type"] = "CONGESTION_ALERT"
        payload["affected_users"] = max(int(payload.get("affected_users", 100)), 500)


def stream_status_payload(session) -> dict[str, Any]:
    return {
        "stream_id": session.id,
        "domain": session.domain,
        "status": session.status,
        "events_generated": session.events_generated,
        "events_failed": session.events_failed,
        "started_at": session.started_at,
        "estimated_end_at": session.estimated_end_at,
        "completed_at": session.completed_at,
        "failure_summary": json.loads(session.failure_summary or "{}"),
        "webhook_delivery_summary": json.loads(session.webhook_delivery_summary or "{}"),
    }


def stream_event_payload(row) -> dict[str, Any]:
    return {
        "event_id": row.event_id,
        "event_type": row.event_type,
        "domain": row.domain,
        "event_time": row.event_time.isoformat(),
        "ingestion_time": row.ingestion_time.isoformat(),
        "sequence_number": row.sequence_number,
        "correlation_id": row.correlation_id,
        "payload": json.loads(row.payload),
        "injected_issues": json.loads(row.injected_issues),
    }


def serialize_stream_event(event: dict[str, Any]) -> dict[str, Any]:
    return {
        **event,
        "event_time": event["event_time"].isoformat(),
        "ingestion_time": event["ingestion_time"].isoformat(),
    }


def generate_stream_token() -> str:
    return f"dfst_{secrets.token_urlsafe(32)}"


def hash_stream_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def store_ephemeral_webhook_secret(stream_id: str, webhook_secret: str) -> None:
    with _WEBHOOK_SECRET_LOCK:
        _WEBHOOK_SECRET_CACHE[stream_id] = webhook_secret


def pop_ephemeral_webhook_secret(stream_id: str) -> str | None:
    with _WEBHOOK_SECRET_LOCK:
        return _WEBHOOK_SECRET_CACHE.pop(stream_id, None)


def sign_webhook_payload(payload: str, webhook_secret: str | None) -> str:
    secret = (webhook_secret or "").encode("utf-8")
    return hmac.new(secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()


def deliver_webhook_event(webhook_url: str, webhook_secret: str | None, event: dict[str, Any]) -> dict[str, Any]:
    safe_url = validate_webhook_url(webhook_url)
    body = json.dumps({"event": event}, separators=(",", ":"), sort_keys=True)
    signature = sign_webhook_payload(body, webhook_secret)
    req = urlrequest.Request(
        safe_url,
        data=body.encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-DataForge-Signature": f"sha256={signature}",
        },
        method="POST",
    )
    last_response_code: int | None = None
    last_error: str | None = None
    for attempt in range(1, WEBHOOK_MAX_RETRIES + 1):
        try:
            with _webhook_opener().open(req, timeout=5) as response:
                last_response_code = response.status
                if 200 <= response.status < 300:
                    return {"status": "delivered", "attempts": attempt, "last_response_code": last_response_code, "last_error": None}
                location = response.headers.get("Location")
                if 300 <= response.status < 400 and location:
                    validate_webhook_url(location)
                last_error = f"HTTP {response.status}"
        except (TimeoutError, URLError, OSError) as exc:
            last_error = str(exc)
    return {"status": "failed", "attempts": WEBHOOK_MAX_RETRIES, "last_response_code": last_response_code, "last_error": last_error}


def validate_webhook_url(webhook_url: str) -> str:
    parsed = urlparse(webhook_url)
    if parsed.scheme.lower() != "https":
        raise ValueError("webhook_url must use https://")
    if not parsed.hostname:
        raise ValueError("webhook_url must include a hostname")
    hostname = parsed.hostname.strip().lower().rstrip(".")
    if _is_disallowed_hostname(hostname):
        raise ValueError("webhook_url cannot target localhost, private networks, or cloud metadata services")

    settings = get_settings()
    allowed_domains = settings.webhook_allowed_domains
    if settings.app_env.lower() == "production":
        if not allowed_domains:
            raise ValueError("WEBHOOK_ALLOWED_DOMAINS is required before webhook delivery in production")
        if not any(hostname == domain or hostname.endswith(f".{domain}") for domain in allowed_domains):
            raise ValueError("webhook_url host is not in WEBHOOK_ALLOWED_DOMAINS")
    elif allowed_domains and not any(hostname == domain or hostname.endswith(f".{domain}") for domain in allowed_domains):
        raise ValueError("webhook_url host is not in WEBHOOK_ALLOWED_DOMAINS")

    return webhook_url


def _is_disallowed_hostname(hostname: str) -> bool:
    if hostname in {"localhost", "localhost.localdomain"} or hostname.endswith(".localhost"):
        return True
    try:
        return _is_disallowed_ip(ipaddress.ip_address(hostname))
    except ValueError:
        return any(_is_disallowed_ip(address) for address in _resolve_hostname(hostname))


def _resolve_hostname(hostname: str) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    try:
        infos = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    except socket.gaierror:
        if get_settings().app_env.lower() == "production":
            raise ValueError("webhook_url hostname could not be resolved")
        return []
    addresses = []
    for info in infos:
        addresses.append(ipaddress.ip_address(info[4][0]))
    return addresses


def _is_disallowed_ip(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
        or address in CLOUD_METADATA_IPS
    )


class _NoRedirectHandler(urlrequest.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_webhook_url(newurl)
        return None


def _webhook_opener():
    return urlrequest.build_opener(_NoRedirectHandler)


def _aware_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def stream_validation_report(session, events: Iterable[Any]) -> dict[str, Any]:
    summary = json.loads(session.failure_summary or "{}")
    metadata = json.loads(session.webhook_delivery_summary or "{}").get("scenario_metadata") or {}
    checks = [
        {
            "name": validation_name,
            "status": "FAIL" if summary.get(failure_type, 0) else "PASS",
            "expected": "0",
            "actual": str(summary.get(failure_type, 0)),
        }
        for failure_type, validation_name in STREAM_VALIDATION_NAMES.items()
    ]
    failed = sum(1 for check in checks if check["status"] == "FAIL")
    quality_score = max(0, 100 - failed * 10)
    scenario_validator_results = []
    scenario_outcome = None
    if metadata.get("scenario_id"):
        scenario = get_scenario(metadata["scenario_id"])
        config = ScenarioRunConfig(**metadata.get("scenario_run_config", {"scenario_id": scenario.scenario_id}))
        event_payloads = [stream_event_payload(event) for event in events]
        scenario_validator_results = validate_scenario_events(event_payloads, scenario=scenario, config=config, expected_counts=summary)
        scenario_outcome = scenario_outcome_from_validations(scenario_validator_results)
    return {
        "run_id": session.id,
        "domain": session.domain,
        "load_type": "event_stream",
        "format": session.format,
        "record_count": session.events_generated,
        "quality_score": quality_score,
        "status": "FAIL" if failed else "PASS",
        "summary": {"total_checks": len(checks), "passed": len(checks) - failed, "failed": failed},
        "issues": [{"type": key, "count": value} for key, value in summary.items()],
        "checks": checks,
        "scenario_validator_results": scenario_validator_results,
        "scenario_outcome": scenario_outcome,
        "generated_at": (session.completed_at or datetime.now(timezone.utc)).isoformat(),
    }


def _validate_stream_request(request: StreamStartRequest) -> None:
    if request.domain not in STREAM_EVENT_TYPES:
        raise ValueError(f"Streaming is not supported for domain: {request.domain}")
    supported = set(STREAM_EVENT_TYPES[request.domain])
    invalid_events = set(request.event_types) - supported
    if invalid_events:
        raise ValueError(f"Unsupported event types for {request.domain}: {sorted(invalid_events)}")
    invalid_failures = set(request.failure_injections) - STREAM_FAILURE_TYPES
    if invalid_failures:
        raise ValueError(f"Unsupported streaming failure injections: {sorted(invalid_failures)}")


def _active_failures(failure_injections: dict[str, Any]) -> dict[str, float]:
    active = {}
    for key, value in failure_injections.items():
        if value is True:
            active[key] = 0.05
        elif value:
            active[key] = min(max(float(value), 0.0), 1.0)
    return active


def _failure_indexes(total: int, rate: float, rng: random.Random) -> set[int]:
    if not rate or total < 1:
        return set()
    count = max(1, int(total * rate))
    return set(rng.sample(range(1, total + 1), min(count, total)))


def _should_inject(sequence: int, total: int, rate: float, rng: random.Random) -> bool:
    if not rate:
        return False
    if sequence == 1:
        return True
    return rng.random() < rate


def _event_id(domain: str, seed: int, sequence: int, event_type: str) -> str:
    deterministic = uuid.uuid5(uuid.NAMESPACE_URL, f"dataforge:{domain}:{seed}:{sequence}:{event_type}")
    return str(deterministic)


def _payload_for(domain: str, event_type: str, sequence: int, rng: random.Random) -> dict[str, Any]:
    if domain == "manufacturing":
        base = {
            "factory_id": f"FAC{sequence % 12:03d}",
            "machine_id": f"MC{sequence % 250:05d}",
            "work_order_id": f"WO{100000 + sequence}",
        }
        if event_type == "machine_sensor":
            return {
                **base,
                "temperature_celsius": round(rng.uniform(58, 104), 2),
                "vibration_mm_s": round(rng.uniform(0.2, 8.5), 3),
                "pressure_psi": round(rng.uniform(20, 140), 2),
                "rpm": rng.randrange(600, 3600),
                "sensor_status": rng.choice(["normal", "warning", "critical"]),
            }
        if event_type == "production_event":
            return {
                **base,
                "line_id": f"LINE{sequence % 24:03d}",
                "sku": f"SKU{sequence % 5000:05d}",
                "units_planned": rng.randrange(80, 400),
                "units_produced": rng.randrange(70, 390),
                "cycle_time_seconds": round(rng.uniform(12, 92), 2),
            }
        if event_type == "quality_event":
            inspected = rng.randrange(50, 300)
            defects = rng.randrange(0, max(1, inspected // 12))
            return {
                **base,
                "inspection_id": f"QCI{sequence:08d}",
                "defect_count": defects,
                "sample_size": inspected,
                "defect_rate": round(defects / inspected, 4),
                "severity": rng.choice(["low", "medium", "high", "critical"]),
            }
        if event_type == "maintenance_alert":
            return {
                **base,
                "alert_id": f"MNT{sequence:08d}",
                "alert_type": rng.choice(["bearing_wear", "oil_pressure", "overheating", "calibration_due"]),
                "severity": rng.choice(["low", "medium", "high", "critical"]),
                "recommended_action": rng.choice(["inspect", "schedule_maintenance", "pause_line", "replace_part"]),
            }
        if event_type == "downtime_event":
            return {
                **base,
                "downtime_reason": rng.choice(["planned_maintenance", "material_shortage", "equipment_failure", "quality_hold"]),
                "downtime_minutes": rng.randrange(5, 180),
                "lost_units_estimate": rng.randrange(10, 1200),
                "line_status": rng.choice(["paused", "degraded", "stopped"]),
            }
        return {**base, "metric_value": round(rng.uniform(20, 95), 3)}
    if domain == "telecommunications":
        return {
            "customer_id": f"TEL{100000 + sequence}",
            "subscription_id": f"SUB{sequence % 50000:06d}",
            "tower_id": f"TWR{sequence % 1200:05d}",
            "usage_mb": round(rng.uniform(0.1, 5120), 3),
        }
    if domain == "ecommerce":
        return {
            "customer_id": f"CUST{100000 + sequence}",
            "seller_id": f"SELL{sequence % 5000:05d}",
            "order_id": f"ORD{1000000 + sequence}",
            "amount": round(rng.uniform(5, 500), 2),
        }
    if domain == "logistics":
        return {
            "shipment_id": f"SHP{1000000 + sequence}",
            "vehicle_id": f"VEH{sequence % 5000:05d}",
            "route_id": f"RTE{sequence % 400:04d}",
            "latitude": round(25 + rng.random() * 20, 6),
            "longitude": round(-124 + rng.random() * 55, 6),
        }
    if domain == "banking":
        return {
            "account_id": f"ACCT{100000 + sequence}",
            "transaction_id": f"TXN{10000000 + sequence}",
            "amount": round(rng.uniform(1, 10000), 2),
            "currency": "USD",
        }
    return {"sequence": sequence, "value": rng.random()}
