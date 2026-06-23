from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from .model import FailureEvent
from .modes import ArtifactRows


def _fieldnames(rows: list[dict[str, Any]]) -> list[str]:
    return list(dict.fromkeys(key for row in rows for key in row))


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=_fieldnames(rows))
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(json.dumps(rows, indent=2, default=str), encoding="utf-8")


def _write_parquet(path: Path, rows: list[dict[str, Any]]) -> None:
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as error:
        raise RuntimeError("Parquet output requires pyarrow; install dataforge-retail[parquet]") from error
    normalized = [
        {key: (None if value == "" else value) for key, value in row.items()}
        for row in rows
    ]
    columns = _fieldnames(normalized)
    mixed_columns = {
        column for column in columns
        if len({type(row.get(column)) for row in normalized if row.get(column) is not None}) > 1
    }
    if mixed_columns:
        normalized = [
            {key: (str(value) if key in mixed_columns and value is not None else value) for key, value in row.items()}
            for row in normalized
        ]
    pq.write_table(pa.Table.from_pylist(normalized), path)


def export_run(
    output: Path,
    artifacts: ArtifactRows,
    output_formats: list[str],
    metadata: dict[str, Any],
    reports: dict[str, dict[str, Any]],
    failures: list[FailureEvent],
) -> None:
    output.mkdir(parents=True, exist_ok=True)
    checksums: dict[str, str] = {}
    artifact_metadata: dict[str, Any] = {}
    writers = {"csv": _write_csv, "json": _write_json, "parquet": _write_parquet}
    for relative_name, rows in artifacts.items():
        for output_format in output_formats:
            path = output / f"{relative_name}.{output_format}"
            path.parent.mkdir(parents=True, exist_ok=True)
            writers[output_format](path, rows)
            relative_path = str(path.relative_to(output))
            checksums[relative_path] = hashlib.sha256(path.read_bytes()).hexdigest()
            artifact_metadata[relative_path] = {"rows": len(rows), "columns": _fieldnames(rows), "format": output_format}
    metadata["artifacts"] = artifact_metadata
    metadata["checksums_sha256"] = checksums
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    for filename, report in reports.items():
        (output / filename).write_text(json.dumps(report, indent=2), encoding="utf-8")
    failure_payload = {"total_injected": sum(event.count for event in failures), "events": [event.__dict__ for event in failures]}
    (output / "failure_report.json").write_text(json.dumps(failure_payload, indent=2), encoding="utf-8")
