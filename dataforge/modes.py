from __future__ import annotations

import copy
import json
import random
import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

from .audit import record_hash
from .domains.retail.schemas import RETAIL_SPEC
from .model import Dataset, DomainSpec


class LoadType(str, Enum):
    BULK = "bulk"
    INCREMENTAL = "incremental"
    DELTA = "delta"
    CDC = "cdc"
    EVENT_STREAM = "event_stream"


ArtifactRows = dict[str, list[dict[str, Any]]]


def normalize_load_type(load_type: str) -> str:
    return "event_stream" if load_type == "event" else load_type


def _changed(row: dict[str, Any], operation: str, day: int) -> dict[str, Any]:
    result = copy.deepcopy(row)
    result["change_type"] = operation
    stamp = datetime(2026, 6, 22, tzinfo=timezone.utc) + timedelta(days=day - 1)
    result["updated_ts"] = stamp.isoformat()
    result["ingestion_ts"] = stamp.isoformat()
    result["batch_id"] = f"BATCH-{stamp:%Y%m%d}"
    result["load_id"] = f"{operation}-{stamp:%Y%m%d}"
    if operation == "UPDATED":
        result["record_version"] = int(result["record_version"]) + 1
    if operation == "DELETE":
        result["is_deleted"] = True
    if operation == "LATE_ARRIVING":
        result["source_ts"] = (stamp - timedelta(days=7)).isoformat()
    result["record_hash"] = record_hash(result)
    return result


def _partition_incremental(data: Dataset, seed: int) -> ArtifactRows:
    rng = random.Random(seed + 10)
    artifacts: ArtifactRows = {}
    for table, rows in data.items():
        chunks = [rows[index::3] for index in range(3)]
        seen: list[dict[str, Any]] = []
        for day, chunk in enumerate(chunks, 1):
            late_count = int(len(chunk) * 0.05)
            new_rows = [_changed(row, "LATE_ARRIVING" if index < late_count else "NEW", day) for index, row in enumerate(chunk)]
            update_count = int(len(chunk) * 0.15) if seen else 0
            updates = [_changed(row, "UPDATED", day) for row in rng.sample(seen, min(update_count, len(seen)))]
            artifacts[f"incremental/day_{day}/{table}"] = new_rows + updates
            seen.extend(chunk)
    return artifacts


def _delta(data: Dataset, seed: int, spec: DomainSpec) -> ArtifactRows:
    rng = random.Random(seed + 20)
    artifacts: ArtifactRows = {}
    for table, rows in data.items():
        update_count = int(len(rows) * 0.2)
        delete_count = int(len(rows) * 0.05)
        sample = rng.sample(rows, min(update_count + delete_count, len(rows)))
        updates = {_row[spec.schemas[table].primary_key] for _row in sample[:update_count]}
        deletes = {_row[spec.schemas[table].primary_key] for _row in sample[update_count:]}
        artifacts[f"delta/{table}_delta"] = [
            _changed(row, "DELETE" if row[spec.schemas[table].primary_key] in deletes else ("UPDATED" if row[spec.schemas[table].primary_key] in updates else "NEW"), 1)
            for row in rows
        ]
    return artifacts


def _cdc(data: Dataset, spec: DomainSpec, selected_tables: set[str]) -> ArtifactRows:
    artifacts: ArtifactRows = {}
    for table in spec.cdc_tables:
        if table not in selected_tables or table not in data:
            continue
        schema = spec.schemas[table]
        events: list[dict[str, Any]] = []
        for index, row in enumerate(data[table], 1):
            event_type = "INSERT" if index % 10 < 7 else ("UPDATE" if index % 10 < 9 else "DELETE")
            payload = {key: value for key, value in row.items() if key not in {"ingestion_ts", "load_id"}}
            before = None if event_type == "INSERT" else payload
            after = None if event_type == "DELETE" else payload
            business_key = row[schema.primary_key]
            event_ts = row.get("transaction_ts", row.get("updated_ts"))
            events.append({
                "event_id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"dataforge-{spec.name}-{table}-{business_key}-{event_type}")),
                "event_type": event_type,
                "business_key": business_key,
                "before_value": json.dumps(before, separators=(",", ":"), default=str) if before is not None else "",
                "after_value": json.dumps(after, separators=(",", ":"), default=str) if after is not None else "",
                "event_ts": event_ts,
                "source_ts": row["source_ts"],
                "ingestion_ts": row["ingestion_ts"],
                "batch_id": row["batch_id"],
            })
        artifacts[f"cdc/{table}_cdc"] = events
    return artifacts


def _event_stream(data: Dataset, spec: DomainSpec, selected_tables: set[str]) -> ArtifactRows:
    artifacts: ArtifactRows = {}
    for definition in spec.event_definitions:
        if definition.table not in selected_tables or definition.table not in data:
            continue
        source_rows = data[definition.table]
        if definition.sample_every:
            source_rows = source_rows[1::definition.sample_every]
        rows = []
        for row in source_rows:
            event_ts = row.get(definition.timestamp_column or "", row.get("transaction_ts", row["updated_ts"]))
            business_key = row[definition.key_column]
            rows.append({
                "event_id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"{spec.name}-{definition.name}-{business_key}")),
                "event_type": definition.event_type,
                "event_ts": event_ts,
                "source_ts": row["source_ts"],
                "ingestion_ts": row["ingestion_ts"],
                "correlation_id": str(uuid.uuid5(uuid.NAMESPACE_OID, f"{spec.name}-{business_key}")),
                "business_key": business_key,
                "payload": json.dumps(row, default=str, separators=(",", ":")),
            })
        artifacts[f"events/{definition.name}"] = rows
    return artifacts


def build_artifacts(
    data: Dataset,
    load_type: str,
    seed: int,
    selected_tables: set[str] | None = None,
    spec: DomainSpec = RETAIL_SPEC,
) -> ArtifactRows:
    normalized = normalize_load_type(load_type)
    selected_tables = selected_tables or set(data)
    selected_data = {table: rows for table, rows in data.items() if table in selected_tables}
    if normalized == LoadType.BULK.value:
        return {f"bulk/{table}": rows for table, rows in selected_data.items()}
    if normalized == LoadType.INCREMENTAL.value:
        return _partition_incremental(selected_data, seed)
    if normalized == LoadType.DELTA.value:
        return _delta(selected_data, seed, spec)
    if normalized == LoadType.CDC.value:
        return _cdc(data, spec, selected_tables)
    if normalized == LoadType.EVENT_STREAM.value:
        return _event_stream(data, spec, selected_tables)
    raise ValueError(f"unsupported load type: {load_type}")
