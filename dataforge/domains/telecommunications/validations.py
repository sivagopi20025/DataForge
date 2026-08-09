from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from .constants import (
    CALL_STATUSES,
    CALL_TYPES,
    COVERAGE_TYPES,
    CUSTOMER_STATUSES,
    CUSTOMER_TYPES,
    DELIVERY_STATUSES,
    DEVICE_TYPES,
    INVOICE_STATUSES,
    MESSAGE_TYPES,
    NETWORK_EVENT_STATUSES,
    NETWORK_EVENT_TYPES,
    NETWORK_TYPES,
    OS_TYPES,
    PAYMENT_METHODS,
    PAYMENT_STATUSES,
    PLAN_TYPES,
    SEVERITIES,
    SESSION_STATUSES,
    SIM_STATUSES,
    SUBSCRIPTION_STATUSES,
    SUBSCRIPTION_TYPES,
    TECHNOLOGIES,
    TICKET_PRIORITIES,
    TICKET_STATUSES,
    TICKET_TYPES,
    TOWER_TYPES,
)


def _decimal(value: Any) -> Decimal:
    return Decimal(str(value))


def _dt(value: Any) -> datetime:
    return datetime.fromisoformat(str(value))


def valid_value_validation(data: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    checks = (
        ("customer_type_valid", "telecom_customers", "customer_type", CUSTOMER_TYPES),
        ("customer_status_valid", "telecom_customers", "status", CUSTOMER_STATUSES),
        ("plan_type_valid", "plans", "plan_type", PLAN_TYPES),
        ("subscription_type_valid", "subscriptions", "subscription_type", SUBSCRIPTION_TYPES),
        ("subscription_status_valid", "subscriptions", "status", SUBSCRIPTION_STATUSES),
        ("sim_status_valid", "sim_cards", "status", SIM_STATUSES),
        ("device_type_valid", "devices", "device_type", DEVICE_TYPES),
        ("os_type_valid", "devices", "os_type", OS_TYPES),
        ("coverage_type_valid", "network_regions", "coverage_type", COVERAGE_TYPES),
        ("tower_type_valid", "cell_towers", "tower_type", TOWER_TYPES),
        ("technology_valid", "cell_towers", "technology", TECHNOLOGIES),
        ("call_type_valid", "call_detail_records", "call_type", CALL_TYPES),
        ("call_status_valid", "call_detail_records", "call_status", CALL_STATUSES),
        ("delivery_status_valid", "sms_records", "delivery_status", DELIVERY_STATUSES),
        ("message_type_valid", "sms_records", "message_type", MESSAGE_TYPES),
        ("network_type_valid", "data_sessions", "network_type", NETWORK_TYPES),
        ("session_status_valid", "data_sessions", "session_status", SESSION_STATUSES),
        ("payment_method_valid", "billing_accounts", "payment_method", PAYMENT_METHODS),
        ("invoice_status_valid", "invoices", "status", INVOICE_STATUSES),
        ("payment_status_valid", "payments", "payment_status", PAYMENT_STATUSES),
        ("network_event_type_valid", "network_events", "event_type", NETWORK_EVENT_TYPES),
        ("network_event_severity_valid", "network_events", "severity", SEVERITIES),
        ("network_event_status_valid", "network_events", "status", NETWORK_EVENT_STATUSES),
        ("ticket_type_valid", "support_tickets", "ticket_type", TICKET_TYPES),
        ("ticket_priority_valid", "support_tickets", "priority", TICKET_PRIORITIES),
        ("ticket_status_valid", "support_tickets", "status", TICKET_STATUSES),
    )
    return [
        {"check": name, "table": table, "failures": sum(1 for row in data.get(table, []) if row.get(column) not in allowed)}
        for name, table, column, allowed in checks
    ]


def call_duration_validation(data: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    failures = 0
    for row in data.get("call_detail_records", []):
        try:
            start = _dt(row["call_start_time"])
            end = _dt(row["call_end_time"])
            duration = int(row["duration_seconds"])
            failures += end <= start
            failures += abs(int((end - start).total_seconds()) - duration) > 1
            failures += duration < 0
        except (KeyError, ValueError, TypeError):
            failures += 1
    return [{"check": "call_duration_matches_start_and_end", "table": "call_detail_records", "failures": failures}]


def data_session_validation(data: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    failures = 0
    for row in data.get("data_sessions", []):
        try:
            failures += _dt(row["session_end_time"]) <= _dt(row["session_start_time"])
            failures += _decimal(row["data_used_mb"]) < 0
            failures += _decimal(row["cost"]) < 0
        except (InvalidOperation, KeyError, ValueError, TypeError):
            failures += 1
    return [{"check": "data_session_time_and_usage_valid", "table": "data_sessions", "failures": failures}]


def invoice_total_validation(data: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    failures = 0
    for row in data.get("invoices", []):
        try:
            expected = _decimal(row["total_voice_charges"]) + _decimal(row["total_sms_charges"]) + _decimal(row["total_data_charges"]) + _decimal(row["taxes"])
            failures += abs(expected - _decimal(row["total_amount"])) > Decimal("0.02")
        except (InvalidOperation, KeyError):
            failures += 1
    return [{"check": "invoice_total_equals_charges_plus_taxes", "table": "invoices", "failures": failures}]


def payment_validation(data: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    failures = 0
    for row in data.get("payments", []):
        try:
            failures += _decimal(row["payment_amount"]) < 0
        except (InvalidOperation, KeyError):
            failures += 1
    return [{"check": "payment_amount_non_negative", "table": "payments", "failures": failures}]


def network_event_validation(data: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    failures = 0
    for row in data.get("network_events", []):
        try:
            failures += int(row["affected_users"]) < 0
            failures += _dt(row["event_end_time"]) <= _dt(row["event_start_time"])
        except (KeyError, ValueError, TypeError):
            failures += 1
    return [{"check": "network_event_time_and_affected_users_valid", "table": "network_events", "failures": failures}]


def support_ticket_validation(data: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    failures = 0
    for row in data.get("support_tickets", []):
        try:
            failures += _dt(row["resolved_at"]) <= _dt(row["opened_at"])
        except (KeyError, ValueError, TypeError):
            failures += 1
    return [{"check": "support_ticket_resolution_after_open", "table": "support_tickets", "failures": failures}]


BUSINESS_RULES = (
    valid_value_validation,
    call_duration_validation,
    data_session_validation,
    invoice_total_validation,
    payment_validation,
    network_event_validation,
    support_ticket_validation,
)
