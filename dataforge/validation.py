from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from .domains.retail.schemas import RETAIL_SPEC
from .model import AUDIT_COLUMNS, Dataset, DomainSpec, SCD2_COLUMNS, TIME_HIERARCHY_COLUMNS
from .reporting import build_validation_report


def _actual_columns(rows: list[dict[str, Any]]) -> list[str]:
    return list(dict.fromkeys(key for row in rows for key in row))


def _schema_drift_checks(rows: list[dict[str, Any]], expected_columns: tuple[str, ...], table: str) -> list[dict[str, Any]]:
    actual_columns = _actual_columns(rows)
    expected = list(expected_columns)
    expected_set = set(expected)
    actual_set = set(actual_columns)
    missing = [column for column in expected if column not in actual_set]
    extra = [column for column in actual_columns if column not in expected_set]
    order_matches = [column for column in actual_columns if column in expected_set] == [column for column in expected if column in actual_set]
    checks = [
        {
            "check": "schema_columns_match",
            "table": table,
            "expected": {"missing": [], "extra": []},
            "actual": {"missing": missing, "extra": extra},
            "failures": len(missing) + len(extra),
            "status": "PASS" if not missing and not extra else "FAIL",
        },
        {
            "check": "schema_column_order",
            "table": table,
            "expected": "expected_order",
            "actual": "expected_order" if order_matches else "column_order_changed",
            "failures": 0 if order_matches else 1,
            "status": "PASS" if order_matches else "FAIL",
        },
    ]
    if missing and extra:
        checks.append({
            "check": "schema_renamed_column_suspected",
            "table": table,
            "expected": missing[0],
            "actual": extra[0],
            "failures": 1,
            "status": "FAIL",
        })
    return checks


def validate(
    data: Dataset,
    spec: DomainSpec = RETAIL_SPEC,
    selected_tables: set[str] | None = None,
    *,
    run_id: str = "",
    load_type: str = "",
    file_format: str = "",
    record_count: int | None = None,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    tables_to_check = selected_tables or set(spec.schemas)
    for table, schema in spec.schemas.items():
        if table not in tables_to_check:
            continue
        rows = data.get(table, [])
        if not rows:
            checks.append({
                "check": "table_has_rows",
                "table": table,
                "failures": 0,
                "status": "PASS",
                "expected": "zero_or_more_rows",
                "actual": 0,
                "message": "Valid empty table for records=0 or empty selected output.",
            })
            continue
        checks.extend(_schema_drift_checks(rows, schema.columns, table))
        scd2 = bool(rows and rows[0].get("effective_start_ts"))
        if schema.primary_key not in rows[0]:
            checks.append({"check": "primary_key_unique", "table": table, "column": schema.primary_key, "failures": len(rows), "status": "FAIL", "expected": "unique", "actual": "missing_primary_key"})
            continue
        keys = [
            (row.get(schema.primary_key), row.get("record_version")) if scd2 else row.get(schema.primary_key)
            for row in rows
        ]
        duplicate_count = len(keys) - len(set(keys))
        checks.append({"check": "primary_key_unique", "table": table, "column": schema.primary_key, "failures": duplicate_count, "status": "PASS" if duplicate_count == 0 else "FAIL"})
        nullable_columns = {fk.column for fk in schema.foreign_keys if fk.nullable} | set(SCD2_COLUMNS)
        for column in schema.columns:
            if column in nullable_columns:
                continue
            if column not in rows[0]:
                continue
            failures = sum(1 for row in rows if row.get(column) in ("", None))
            checks.append({"check": "not_null", "table": table, "column": column, "failures": failures, "status": "PASS" if failures == 0 else "FAIL"})
        for fk in schema.foreign_keys:
            if fk.column not in rows[0]:
                continue
            parent_values = {row[fk.parent_column] for row in data.get(fk.parent_table, [])}
            failures = 0
            for row in rows:
                value = row.get(fk.column)
                try:
                    invalid = value not in parent_values
                except TypeError:
                    invalid = True
                failures += invalid and not (fk.nullable and value in ("", None))
            checks.append({"check": "referential_integrity", "table": table, "column": fk.column, "failures": failures, "status": "PASS" if failures == 0 else "FAIL"})

        business_columns = [column for column in schema.columns if column not in set(AUDIT_COLUMNS) | set(TIME_HIERARCHY_COLUMNS) | set(SCD2_COLUMNS)]
        for column in business_columns:
            if column not in rows[0]:
                continue
            values = [row[column] for row in rows if row.get(column) not in ("", None)]
            if not values:
                continue
            expected_type = max({type(value) for value in values}, key=lambda kind: sum(isinstance(value, kind) for value in values))
            failures = sum(1 for value in values if not isinstance(value, expected_type))
            checks.append({"check": "consistent_datatype", "table": table, "column": column, "expected_type": expected_type.__name__, "failures": failures, "status": "PASS" if failures == 0 else "FAIL"})

        date_column = spec.date_columns.get(table)
        if date_column and date_column in rows[0]:
            invalid_dates_for_table = 0
            for row in rows:
                try:
                    datetime.fromisoformat(str(row.get(date_column)))
                except (TypeError, ValueError):
                    invalid_dates_for_table += 1
            checks.append({"check": "valid_datetime", "table": table, "column": date_column, "failures": invalid_dates_for_table, "status": "PASS" if invalid_dates_for_table == 0 else "FAIL"})

        numeric_column = spec.numeric_columns.get(table)
        if numeric_column and numeric_column in rows[0]:
            negative = 0
            extreme = 0
            invalid_numeric = 0
            for row in rows:
                try:
                    value = Decimal(str(row.get(numeric_column)))
                    negative += value < 0
                    extreme += abs(value) >= Decimal("1000000")
                except InvalidOperation:
                    invalid_numeric += 1
            for name, failures in (("numeric_type", invalid_numeric), ("non_negative", negative), ("outlier_threshold", extreme)):
                checks.append({"check": name, "table": table, "column": numeric_column, "failures": failures, "status": "PASS" if failures == 0 else "FAIL"})

    if selected_tables is None or tables_to_check == set(spec.schemas):
        rules = spec.business_rules
    else:
        rules = ()
    for rule in rules:
        try:
            rule_results = rule(data)
        except (KeyError, TypeError, ValueError) as error:
            rule_results = [{"check": getattr(rule, "__name__", "business_rule"), "table": "business_rules", "failures": 1, "actual": str(error)}]
        for item in rule_results:
            failures = int(item.get("failures", 0))
            item["status"] = "PASS" if failures == 0 else "FAIL"
            item.setdefault("check", "business_rule")
            checks.append(item)
    return build_validation_report(
        checks=checks,
        data=data,
        spec=spec,
        run_id=run_id,
        load_type=load_type,
        file_format=file_format,
        record_count=record_count,
    )


def relationship_report(data: Dataset, spec: DomainSpec = RETAIL_SPEC, selected_tables: set[str] | None = None) -> dict[str, Any]:
    relationships = []
    tables_to_check = selected_tables or set(spec.schemas)
    for table, schema in spec.schemas.items():
        if table not in tables_to_check:
            continue
        for fk in schema.foreign_keys:
            parent_values = {row[fk.parent_column] for row in data.get(fk.parent_table, [])}
            invalid = sum(1 for row in data.get(table, []) if row.get(fk.column) not in parent_values and not (fk.nullable and row.get(fk.column) in ("", None)))
            relationships.append({
                "child_table": table,
                "child_column": fk.column,
                "parent_table": fk.parent_table,
                "parent_column": fk.parent_column,
                "invalid_records": invalid,
                "status": "PASS" if invalid == 0 else "FAIL",
            })
    return {"overall_status": "PASS" if all(item["status"] == "PASS" for item in relationships) else "FAIL", "relationships": relationships}


def schema_report(data: Dataset, spec: DomainSpec = RETAIL_SPEC, selected_tables: set[str] | None = None) -> dict[str, Any]:
    tables = []
    tables_to_check = selected_tables or set(spec.schemas)
    for table, schema in spec.schemas.items():
        if table not in tables_to_check:
            continue
        rows = data.get(table, [])
        actual_columns = _actual_columns(rows) if rows else list(schema.columns)
        actual = set(actual_columns) if rows else set()
        if not rows:
            actual = set(schema.columns)
        missing = [column for column in schema.columns if column not in actual]
        extra = [column for column in actual_columns if column not in set(schema.columns)]
        expected_order = [column for column in schema.columns if column in actual]
        actual_order = [column for column in actual_columns if column in set(schema.columns)]
        required_audit_missing = [column for column in AUDIT_COLUMNS if column not in actual]
        time_missing = [column for column in TIME_HIERARCHY_COLUMNS if table in spec.fact_tables and column not in actual]
        tables.append({
            "table": table,
            "primary_key": schema.primary_key,
            "expected_columns": list(schema.columns),
            "actual_columns": sorted(actual),
            "missing_columns": missing,
            "extra_columns": extra,
            "column_order_changed": expected_order != actual_order,
            "missing_mandatory_audit_columns": required_audit_missing,
            "missing_time_hierarchy_columns": time_missing,
            "status": "PASS" if not missing and not extra and expected_order == actual_order and not required_audit_missing and not time_missing else "FAIL",
        })
    return {"overall_status": "PASS" if all(item["status"] == "PASS" for item in tables) else "FAIL", "tables": tables}


def reconciliation_report(data: Dataset, spec: DomainSpec = RETAIL_SPEC, selected_tables: set[str] | None = None) -> dict[str, Any]:
    tables_to_check = selected_tables or set(spec.schemas)
    if spec.name == "retail" and {"sales", "payments"} <= tables_to_check:
        sales_by_id = {row["sale_id"]: row for row in data["sales"]}
        payment_ids = {row["sale_id"] for row in data["payments"]}
        missing_payments = len(set(sales_by_id) - payment_ids)
        amount_mismatches = 0
        invalid_amounts = 0
        for payment in data["payments"]:
            sale = sales_by_id.get(payment["sale_id"])
            if sale is None:
                continue
            try:
                amount_mismatches += Decimal(str(payment.get("amount"))) != Decimal(str(sale.get("sale_amount")))
            except (InvalidOperation, TypeError):
                invalid_amounts += 1
        checks = [
            {"check": "sales_have_payments", "expected": len(sales_by_id), "actual": len(payment_ids & set(sales_by_id)), "failures": missing_payments},
            {"check": "payment_amount_matches_sale", "expected": 0, "actual": amount_mismatches, "failures": amount_mismatches},
            {"check": "reconcilable_amount_types", "expected": 0, "actual": invalid_amounts, "failures": invalid_amounts},
        ]
    elif spec.name == "logistics" and {"shipments", "tracking_events"} <= tables_to_check:
        shipment_ids = {row["shipment_id"] for row in data.get("shipments", [])}
        tracking_shipments = {row["shipment_id"] for row in data.get("tracking_events", [])}
        delivery_shipments = {row["shipment_id"] for row in data.get("delivery_records", [])}
        checks = [
            {"check": "shipments_have_tracking_events", "expected": len(shipment_ids), "actual": len(shipment_ids & tracking_shipments), "failures": len(shipment_ids - tracking_shipments)},
            {"check": "deliveries_reference_shipments", "expected": len(delivery_shipments), "actual": len(delivery_shipments & shipment_ids), "failures": len(delivery_shipments - shipment_ids)},
        ]
    else:
        checks = [{"check": "reconciliation_not_applicable_for_selection", "expected": 0, "actual": 0, "failures": 0}]
    for check in checks:
        check["status"] = "PASS" if check["failures"] == 0 else "FAIL"
    return {"overall_status": "PASS" if all(check["status"] == "PASS" for check in checks) else "FAIL", "checks": checks}
