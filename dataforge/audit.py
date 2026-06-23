from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
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
    if scd_type == 2:
        for table in spec.dimension_tables:
            rows = data.get(table, [])
            history = []
            for current in rows[:max(1, len(rows) // 10)]:
                previous = copy.deepcopy(current)
                previous["is_current"] = False
                previous["effective_end_ts"] = ingestion.isoformat()
                previous["record_hash"] = record_hash(previous)
                history.append(previous)
                current["record_version"] = 2
                current["effective_start_ts"] = ingestion.isoformat()
                current["updated_ts"] = ingestion.isoformat()
                current["record_hash"] = record_hash(current)
            rows.extend(history)
    return data
