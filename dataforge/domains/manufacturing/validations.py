from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from .constants import (
    BATCH_STATUSES,
    DEFECT_TYPES,
    EMPLOYEE_ROLES,
    FACTORY_TYPES,
    INVENTORY_TYPES,
    MACHINE_TYPES,
    MAINTENANCE_TYPES,
    QUALITY_RESULTS,
    SEVERITIES,
    WORK_ORDER_STATUSES,
)


def _decimal(value: Any) -> Decimal:
    return Decimal(str(value))


def valid_value_validation(data: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    checks = (
        ("factory_type_valid", "factories", "factory_type", FACTORY_TYPES),
        ("machine_type_valid", "machines", "machine_type", MACHINE_TYPES),
        ("work_order_status_valid", "work_orders", "status", WORK_ORDER_STATUSES),
        ("batch_status_valid", "production_batches", "batch_status", BATCH_STATUSES),
        ("quality_result_valid", "quality_checks", "result", QUALITY_RESULTS),
        ("defect_type_valid", "defects", "defect_type", DEFECT_TYPES),
        ("defect_severity_valid", "defects", "severity", SEVERITIES),
        ("maintenance_type_valid", "maintenance_orders", "maintenance_type", MAINTENANCE_TYPES),
        ("employee_role_valid", "employees", "role", EMPLOYEE_ROLES),
        ("inventory_type_valid", "inventory", "inventory_type", INVENTORY_TYPES),
    )
    return [
        {"check": name, "table": table, "failures": sum(1 for row in data.get(table, []) if row.get(column) not in allowed)}
        for name, table, column, allowed in checks
    ]


def quantity_validation(data: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    work_order_failures = 0
    for row in data.get("work_orders", []):
        try:
            planned = _decimal(row["planned_quantity"])
            produced = _decimal(row["produced_quantity"])
            rejected = _decimal(row["rejected_quantity"])
            work_order_failures += planned < 0 or produced < 0 or rejected < 0 or produced > planned * Decimal("1.10") or rejected > produced
        except (InvalidOperation, KeyError):
            work_order_failures += 1

    batch_failures = 0
    for row in data.get("production_batches", []):
        try:
            produced = _decimal(row["quantity_produced"])
            rejected = _decimal(row["quantity_rejected"])
            batch_failures += produced < 0 or rejected < 0 or rejected > produced
        except (InvalidOperation, KeyError):
            batch_failures += 1

    return [
        {"check": "work_order_quantities_consistent", "table": "work_orders", "failures": work_order_failures},
        {"check": "batch_quantities_consistent", "table": "production_batches", "failures": batch_failures},
    ]


def quality_alignment_validation(data: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    failures = 0
    for row in data.get("quality_checks", []):
        try:
            defect_count = _decimal(row["defect_count"])
            pass_percentage = _decimal(row["pass_percentage"])
            failures += defect_count < 0 or pass_percentage < 0 or pass_percentage > 100
            if defect_count == 0:
                failures += pass_percentage < 95
            elif defect_count > 0:
                failures += pass_percentage > 99
        except (InvalidOperation, KeyError):
            failures += 1
    return [{"check": "quality_pass_percentage_aligns_with_defects", "table": "quality_checks", "failures": failures}]


def maintenance_validation(data: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    failures = 0
    for row in data.get("maintenance_orders", []):
        try:
            downtime = _decimal(row["downtime_minutes"])
            cost = _decimal(row["cost"])
            failures += downtime < 0 or cost < 0
            scheduled = datetime.fromisoformat(str(row["scheduled_time"]))
            completed_raw = row.get("completed_time")
            if completed_raw:
                completed = datetime.fromisoformat(str(completed_raw))
                failures += completed < scheduled
        except (InvalidOperation, KeyError, ValueError):
            failures += 1
    return [{"check": "maintenance_downtime_and_cost_non_negative", "table": "maintenance_orders", "failures": failures}]


def inventory_item_validation(data: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    failures = 0
    for row in data.get("inventory", []):
        material_id = row.get("material_id")
        product_id = row.get("product_id")
        inventory_type = row.get("inventory_type")
        failures += inventory_type == "raw_material" and not material_id
        failures += inventory_type == "finished_good" and not product_id
        failures += bool(material_id) and bool(product_id)
        try:
            failures += _decimal(row["quantity_on_hand"]) < 0 or _decimal(row["reorder_level"]) < 0
        except (InvalidOperation, KeyError):
            failures += 1
    return [{"check": "inventory_references_exactly_one_item_type", "table": "inventory", "failures": failures}]


def sensor_reading_validation(data: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    expected_units = {
        "temperature": "celsius",
        "vibration": "mm_s",
        "pressure": "psi",
        "current": "ampere",
    }
    failures = 0
    for row in data.get("sensor_readings", []):
        try:
            sensor_type = row.get("sensor_type")
            quality_flag = row.get("quality_flag")
            failures += sensor_type not in expected_units
            failures += row.get("unit") != expected_units.get(sensor_type)
            failures += _decimal(row["measurement"]) < 0
            failures += quality_flag not in {"normal", "warning", "critical"}
            if quality_flag == "normal":
                failures += row.get("reason_code") != "not_applicable"
            else:
                failures += row.get("reason_code") == "not_applicable"
            datetime.fromisoformat(str(row["reading_timestamp"]))
        except (InvalidOperation, KeyError, ValueError, TypeError):
            failures += 1
    return [{"check": "sensor_reading_measurement_and_flag_valid", "table": "sensor_readings", "failures": failures}]


BUSINESS_RULES = (
    valid_value_validation,
    quantity_validation,
    quality_alignment_validation,
    maintenance_validation,
    inventory_item_validation,
    sensor_reading_validation,
)
