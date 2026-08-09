from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from .canonical import column_order
from .exporter import _write_csv, _write_json, _write_parquet
from .model import DomainSpec, FailureEvent
from .modes import ArtifactRows


def has_schema_drift(failures: list[FailureEvent]) -> bool:
    return any(event.failure_type.startswith("schema_drift") for event in failures)


def export_schema_versions(
    output: Path,
    artifacts: ArtifactRows,
    output_formats: list[str],
    spec: DomainSpec,
    failures: list[FailureEvent],
) -> dict[str, Any] | None:
    drift_events = [event for event in failures if event.failure_type.startswith("schema_drift")]
    if not drift_events:
        return None

    writers = {"csv": _write_csv, "json": _write_json, "parquet": _write_parquet}
    diff: dict[str, Any] = {"status": "DETECTED", "tables": {}}
    for relative_name, rows in artifacts.items():
        table = relative_name.split("/")[-1]
        if table not in spec.schemas:
            continue
        table_events = [event for event in drift_events if event.table == table]
        if not table_events:
            continue
        v1_rows = rows
        v1_columns = column_order(spec, table)
        v2_rows, v2_columns, changes = _apply_schema_version_changes(v1_rows, v1_columns, table_events)
        diff["tables"][table] = {"changes": changes, "v1_columns": v1_columns, "v2_columns": v2_columns}
        for output_format in output_formats:
            v1_path = output / "schema_versions" / "v1" / f"{table}.{output_format}"
            v2_path = output / "schema_versions" / "v2" / f"{table}.{output_format}"
            v1_path.parent.mkdir(parents=True, exist_ok=True)
            v2_path.parent.mkdir(parents=True, exist_ok=True)
            writers[output_format](v1_path, v1_rows, v1_columns)
            writers[output_format](v2_path, v2_rows, v2_columns)
    reports_dir = output / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "schema_diff.json").write_text(json.dumps(diff, indent=2, default=str), encoding="utf-8")
    return diff


def _apply_schema_version_changes(rows: list[dict[str, Any]], columns: list[str], events: list[FailureEvent]) -> tuple[list[dict[str, Any]], list[str], list[dict[str, Any]]]:
    v2_rows = copy.deepcopy(rows)
    v2_columns = list(columns)
    changes: list[dict[str, Any]] = []
    for event in events:
        drift_type = event.details.get("drift_type")
        column = event.column
        if drift_type == "column_added":
            added = column or "schema_drift_added_column"
            if added not in v2_columns:
                v2_columns.append(added)
                for row in v2_rows:
                    row[added] = "drift"
            changes.append({"type": "column_added", "column": added})
        elif drift_type == "column_removed" and column:
            v2_columns = [item for item in v2_columns if item != column]
            for row in v2_rows:
                row.pop(column, None)
            changes.append({"type": "column_removed", "column": column})
        elif drift_type == "column_renamed" and column:
            renamed = event.details.get("renamed_to", f"{column}_renamed")
            v2_columns = [renamed if item == column else item for item in v2_columns]
            for row in v2_rows:
                if column in row:
                    row[renamed] = row.pop(column)
            changes.append({"type": "column_renamed", "from": column, "to": renamed})
        elif drift_type == "datatype_changed" and column:
            for row in v2_rows:
                if column in row:
                    row[column] = str(row[column])
            changes.append({"type": "datatype_changed", "column": column, "new_type": event.details.get("new_type", "string")})
        elif drift_type == "nullability_changed" and column:
            changes.append({"type": "nullability_changed", "column": column, "nullable": event.details.get("nullable", True)})
        elif drift_type == "column_order_changed":
            v2_columns = list(reversed(v2_columns))
            changes.append({"type": "column_order_changed"})
    return v2_rows, v2_columns, changes
