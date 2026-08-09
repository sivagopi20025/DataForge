from __future__ import annotations

from datetime import datetime
from typing import Any

from ...model import DomainSpec, EventDefinition, ForeignKey, TableSchema, with_enterprise_columns


BASE_SCHEMAS: dict[str, TableSchema] = {
    "customers": TableSchema("customer_id", ("customer_id", "customer_name", "customer_type", "email", "phone", "country", "state", "city", "postal_code", "created_at")),
    "warehouses": TableSchema("warehouse_id", ("warehouse_id", "warehouse_name", "country", "state", "city", "postal_code", "capacity", "latitude", "longitude")),
    "drivers": TableSchema("driver_id", ("driver_id", "driver_name", "license_number", "phone", "status", "hire_date")),
    "vehicles": TableSchema("vehicle_id", ("vehicle_id", "vehicle_number", "vehicle_type", "capacity_kg", "driver_id", "status"), (ForeignKey("driver_id", "drivers", "driver_id"),)),
    "shipments": TableSchema("shipment_id", ("shipment_id", "customer_id", "source_warehouse_id", "destination_warehouse_id", "shipment_type", "weight_kg", "volume_cbm", "shipment_status", "created_at"), (ForeignKey("customer_id", "customers", "customer_id"), ForeignKey("source_warehouse_id", "warehouses", "warehouse_id"), ForeignKey("destination_warehouse_id", "warehouses", "warehouse_id"))),
    "delivery_records": TableSchema("delivery_id", ("delivery_id", "shipment_id", "driver_id", "delivery_date", "delivery_status", "delivery_time_minutes"), (ForeignKey("shipment_id", "shipments", "shipment_id"), ForeignKey("driver_id", "drivers", "driver_id"))),
    "tracking_events": TableSchema("event_id", ("event_id", "shipment_id", "event_type", "event_timestamp", "location"), (ForeignKey("shipment_id", "shipments", "shipment_id"),)),
    "exception_alerts": TableSchema("exception_alert_id", ("exception_alert_id", "shipment_id", "source_event_id", "alert_type", "alert_timestamp", "severity", "status", "exception_reason", "reason_code", "estimated_impact_cost", "resolved_at", "created_at"), (ForeignKey("shipment_id", "shipments", "shipment_id"), ForeignKey("source_event_id", "tracking_events", "event_id", nullable=True))),
    "gps_events": TableSchema("event_id", ("event_id", "vehicle_id", "latitude", "longitude", "speed", "timestamp"), (ForeignKey("vehicle_id", "vehicles", "vehicle_id"),)),
}

FACT_TABLES = {"shipments", "delivery_records", "tracking_events", "exception_alerts", "gps_events"}
DIMENSION_TABLES = {"customers", "warehouses", "drivers", "vehicles"}


def _delivery_requires_shipment(data: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    shipment_ids = {row["shipment_id"] for row in data.get("shipments", [])}
    failures = sum(1 for row in data.get("delivery_records", []) if row.get("shipment_id") not in shipment_ids)
    return [{"check": "delivery_cannot_exist_without_shipment", "table": "delivery_records", "failures": failures}]


def _vehicle_must_have_driver(data: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    driver_ids = {row["driver_id"] for row in data.get("drivers", [])}
    failures = sum(1 for row in data.get("vehicles", []) if row.get("driver_id") not in driver_ids)
    return [{"check": "vehicle_must_have_driver", "table": "vehicles", "failures": failures}]


def _tracking_events_follow_valid_order(data: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    rank = {"created": 1, "packed": 2, "in_transit": 3, "delivery_attempted": 4, "delivered": 5, "returned": 6}
    failures = 0
    by_shipment: dict[Any, list[dict[str, Any]]] = {}
    for event in data.get("tracking_events", []):
        by_shipment.setdefault(event.get("shipment_id"), []).append(event)
    for events in by_shipment.values():
        ordered = sorted(events, key=lambda row: str(row.get("event_timestamp")))
        ranks = [rank.get(str(row.get("event_type")), 0) for row in ordered]
        failures += sum(1 for previous, current in zip(ranks, ranks[1:]) if current < previous)
    return [{"check": "tracking_events_follow_valid_order", "table": "tracking_events", "failures": failures}]


def _delivery_not_before_shipment(data: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    shipments = {row["shipment_id"]: row for row in data.get("shipments", [])}
    failures = 0
    for delivery in data.get("delivery_records", []):
        shipment = shipments.get(delivery.get("shipment_id"))
        if not shipment:
            continue
        try:
            failures += datetime.fromisoformat(str(delivery["delivery_date"])) < datetime.fromisoformat(str(shipment["created_at"]))
        except ValueError:
            failures += 1
    return [{"check": "delivery_not_before_shipment_created", "table": "delivery_records", "failures": failures}]


def _exception_alerts_are_business_consistent(data: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    shipments = {row["shipment_id"]: row for row in data.get("shipments", [])}
    tracking_events = {row["event_id"]: row for row in data.get("tracking_events", [])}
    valid_alert_types = {"delay", "temperature_breach", "address_issue", "customs_hold", "damage", "lost_scan"}
    valid_severities = {"low", "medium", "high", "critical"}
    valid_statuses = {"open", "acknowledged", "resolved", "dismissed"}
    invalid_values = 0
    invalid_references = 0
    invalid_timestamps = 0
    invalid_reasons = 0
    for alert in data.get("exception_alerts", []):
        invalid_values += alert.get("alert_type") not in valid_alert_types
        invalid_values += alert.get("severity") not in valid_severities
        invalid_values += alert.get("status") not in valid_statuses
        invalid_references += alert.get("shipment_id") not in shipments
        source_event_id = alert.get("source_event_id")
        if source_event_id not in ("", None, "not_applicable"):
            invalid_references += source_event_id not in tracking_events
        try:
            alert_timestamp = datetime.fromisoformat(str(alert["alert_timestamp"]))
            created_at = datetime.fromisoformat(str(alert["created_at"]))
            invalid_timestamps += created_at > alert_timestamp
            if alert.get("status") == "resolved":
                invalid_timestamps += datetime.fromisoformat(str(alert["resolved_at"])) < alert_timestamp
            else:
                invalid_timestamps += alert.get("resolved_at") != "not_applicable"
            invalid_values += float(alert["estimated_impact_cost"]) < 0
        except (ValueError, TypeError, KeyError):
            invalid_timestamps += 1
        invalid_reasons += alert.get("reason_code") in ("", None)
        invalid_reasons += alert.get("exception_reason") in ("", None)
    return [
        {"check": "exception_alert_values_valid", "table": "exception_alerts", "failures": invalid_values},
        {"check": "exception_alert_references_valid", "table": "exception_alerts", "failures": invalid_references},
        {"check": "exception_alert_timestamps_valid", "table": "exception_alerts", "failures": invalid_timestamps},
        {"check": "exception_alert_reasons_present", "table": "exception_alerts", "failures": invalid_reasons},
    ]


LOGISTICS_SPEC = DomainSpec(
    name="logistics",
    source_system="DATAFORGE_LOGISTICS",
    schemas=with_enterprise_columns(BASE_SCHEMAS, FACT_TABLES, DIMENSION_TABLES),
    fact_tables=FACT_TABLES,
    dimension_tables=DIMENSION_TABLES,
    timestamp_sources={
        "shipments": "created_at",
        "delivery_records": "delivery_date",
        "tracking_events": "event_timestamp",
        "exception_alerts": "alert_timestamp",
        "gps_events": "timestamp",
    },
    date_columns={
        "customers": "created_at",
        "drivers": "hire_date",
        "shipments": "created_at",
        "delivery_records": "delivery_date",
        "tracking_events": "event_timestamp",
        "exception_alerts": "alert_timestamp",
        "gps_events": "timestamp",
    },
    numeric_columns={
        "warehouses": "capacity",
        "vehicles": "capacity_kg",
        "shipments": "weight_kg",
        "delivery_records": "delivery_time_minutes",
        "exception_alerts": "estimated_impact_cost",
        "gps_events": "speed",
    },
    type_mismatch_columns={
        "customers": "customer_name",
        "warehouses": "capacity",
        "drivers": "driver_name",
        "vehicles": "capacity_kg",
        "shipments": "weight_kg",
        "delivery_records": "delivery_time_minutes",
        "tracking_events": "event_type",
        "exception_alerts": "status",
        "gps_events": "speed",
    },
    event_definitions=(
        EventDefinition("tracking_event", "tracking_events", "TRACKING_EVENT", "event_id", "event_timestamp"),
        EventDefinition("exception_alert_event", "exception_alerts", "EXCEPTION_ALERT_UPDATED", "exception_alert_id", "alert_timestamp"),
        EventDefinition("gps_event", "gps_events", "GPS_EVENT", "event_id", "timestamp"),
        EventDefinition("driver_status_event", "drivers", "DRIVER_STATUS_EVENT", "driver_id", "updated_ts"),
    ),
    cdc_tables=("shipments", "delivery_records", "tracking_events", "exception_alerts", "vehicles"),
    business_rules=(_delivery_requires_shipment, _vehicle_must_have_driver, _tracking_events_follow_valid_order, _delivery_not_before_shipment, _exception_alerts_are_business_consistent),
)
