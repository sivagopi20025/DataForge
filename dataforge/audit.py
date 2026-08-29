from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from .model import Dataset, DomainSpec


def _timestamp(value: Any) -> datetime:
    parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def record_hash(row: dict[str, Any]) -> str:
    business = {key: value for key, value in row.items() if key not in {
        "ingestion_ts", "batch_id", "load_id", "record_hash"
    }}
    payload = json.dumps(business, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _scenario_status(row: dict[str, Any]) -> str:
    for column, value in row.items():
        lowered = column.lower()
        if value not in ("", None) and (lowered == "status" or lowered.endswith("_status") or lowered.endswith("_state") or lowered == "active_flag"):
            return str(value)
    return "normal"


def _scenario_amount(row: dict[str, Any], table: str, spec: DomainSpec) -> str:
    preferred = spec.numeric_columns.get(table)
    candidate_columns = [preferred] if preferred else []
    candidate_columns.extend(
        column
        for column in row
        if any(token in column.lower() for token in ("amount", "total", "price", "cost", "balance", "value", "premium", "claim", "settlement", "fee", "quantity"))
    )
    for column in dict.fromkeys(candidate_columns):
        if not column or column not in row:
            continue
        try:
            return str(Decimal(str(row[column])).quantize(Decimal("0.01")))
        except (InvalidOperation, TypeError, ValueError):
            continue
    return "0.00"


def _scenario_group_id(row: dict[str, Any], table: str, spec: DomainSpec) -> str:
    schema = spec.schemas.get(table)
    if not schema:
        return ""
    for fk in schema.foreign_keys:
        value = row.get(fk.column)
        if value not in ("", None):
            return str(value)
    return str(row.get(schema.primary_key, ""))


def _scenario_risk_score(row: dict[str, Any]) -> int:
    payload = json.dumps(row, sort_keys=True, default=str, separators=(",", ":"))
    return 1 + (_stable_int_hash(payload) % 100)


def _stable_int_hash(value: str) -> int:
    return int(hashlib.sha256(value.encode("utf-8")).hexdigest()[:8], 16)


def enrich_dataset(data: Dataset, load_type: str, scd_type: int = 1, spec: DomainSpec | None = None) -> Dataset:
    if spec is None:
        from .domains.retail.schemas import RETAIL_SPEC
        spec = RETAIL_SPEC
    ingestion = datetime.now(timezone.utc)
    batch_id = f"BATCH-{ingestion:%Y%m%d}"
    load_id = f"{load_type.upper()}-{ingestion:%Y%m%dT%H%M%S%fZ}"
    for table, rows in data.items():
        for row in rows:
            timestamp_column = spec.timestamp_sources.get(table) or spec.date_columns.get(table, "")
            source_value = row.get(timestamp_column, ingestion.isoformat())
            source_ts = _timestamp(source_value)
            row.update({
                "created_ts": source_ts.isoformat(),
                "updated_ts": source_ts.isoformat(),
                "source_ts": source_ts.isoformat(),
                "ingestion_ts": ingestion.isoformat(),
                "batch_id": batch_id,
                "load_id": load_id,
                "record_version": 1,
                "is_deleted": False,
                "source_system": spec.source_system,
            })
            scenario_amount = _scenario_amount(row, table, spec)
            row.setdefault("event_timestamp", source_ts.isoformat())
            row.setdefault("scenario_status_code", _scenario_status(row))
            row.setdefault("idempotency_key", hashlib.sha256(f"{spec.name}:{table}:{row.get(spec.schemas[table].primary_key, '')}:v1".encode("utf-8")).hexdigest()[:24])
            row.setdefault("expected_amount", scenario_amount)
            row.setdefault("actual_amount", scenario_amount)
            row.setdefault("reason_code", "none")
            row.setdefault("reconciliation_group_id", _scenario_group_id(row, table, spec))
            row.setdefault("risk_score", _scenario_risk_score(row))
            if table in spec.fact_tables:
                row.update({
                    "transaction_ts": source_ts.isoformat(),
                    "transaction_date": source_ts.date().isoformat(),
                    "transaction_hour": source_ts.hour,
                    "transaction_day": source_ts.day,
                    "transaction_week": source_ts.isocalendar().week,
                    "transaction_month": source_ts.month,
                    "transaction_quarter": ((source_ts.month - 1) // 3) + 1,
                    "transaction_year": source_ts.year,
                })
            if table in spec.dimension_tables:
                row.update({
                    "effective_start_ts": source_ts.isoformat() if scd_type == 2 else "",
                    "effective_end_ts": "" if scd_type == 2 else "",
                    "is_current": True,
                })
            row["record_hash"] = record_hash(row)
            _canonicalize_row_order(row, table, spec)
    if scd_type == 2:
        for table in spec.dimension_tables:
            rows = data.get(table, [])
            history = []
            for current in rows[:max(1, len(rows) // 10)]:
                previous = copy.deepcopy(current)
                previous["is_current"] = False
                previous["effective_end_ts"] = ingestion.isoformat()
                previous["record_hash"] = record_hash(previous)
                _canonicalize_row_order(previous, table, spec)
                history.append(previous)
                current["record_version"] = 2
                current["effective_start_ts"] = ingestion.isoformat()
                current["updated_ts"] = ingestion.isoformat()
                current["record_hash"] = record_hash(current)
                _canonicalize_row_order(current, table, spec)
            rows.extend(history)
    return data


def _canonicalize_row_order(row: dict[str, Any], table: str, spec: DomainSpec) -> None:
    schema = spec.schemas.get(table)
    if not schema:
        return
    ordered = {column: row.get(column, "") for column in schema.columns if column in row}
    ordered.update({column: value for column, value in row.items() if column not in ordered})
    row.clear()
    row.update(ordered)
