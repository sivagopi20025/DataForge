from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from backend.app.models import GeneratedFile
from backend.app.services.storage import LocalStorageService, StorageService


def preview_generated_file(generated_file: GeneratedFile, storage: StorageService, *, max_rows: int = 50) -> dict[str, Any]:
    if not isinstance(storage, LocalStorageService):
        raise ValueError("Preview is currently available for local generated files only")

    path = storage.resolve_path(generated_file)
    suffix = path.suffix.lower()
    if suffix == ".csv":
        columns, rows = _preview_csv(path, max_rows=max_rows)
    elif suffix == ".json":
        columns, rows = _preview_json(path, max_rows=max_rows)
    elif suffix == ".parquet":
        columns, rows = _preview_parquet(path, max_rows=max_rows)
    else:
        raise ValueError(f"Preview is not supported for file type: {suffix}")

    return {
        "file_id": generated_file.id,
        "file_name": generated_file.file_name,
        "file_format": generated_file.file_format,
        "columns": columns,
        "rows": rows,
        "row_count": len(rows),
        "max_rows": max_rows,
    }


def _preview_csv(path: Path, *, max_rows: int) -> tuple[list[str], list[dict[str, Any]]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = [row for _, row in zip(range(max_rows), reader)]
        return list(reader.fieldnames or []), rows


def _preview_json(path: Path, *, max_rows: int) -> tuple[list[str], list[dict[str, Any]]]:
    decoder = json.JSONDecoder()
    rows: list[dict[str, Any]] = []
    buffer = ""
    position = 0
    started = False

    with path.open("r", encoding="utf-8") as handle:
        while len(rows) < max_rows:
            chunk = handle.read(65536)
            if not chunk and position >= len(buffer):
                break
            buffer += chunk

            while len(rows) < max_rows:
                while position < len(buffer) and buffer[position].isspace():
                    position += 1
                if position >= len(buffer):
                    break
                if not started:
                    if buffer[position] == "[":
                        started = True
                        position += 1
                        continue
                    raise ValueError("JSON preview expects an array of objects")
                if buffer[position] == "]":
                    position += 1
                    break
                if buffer[position] == ",":
                    position += 1
                    continue
                try:
                    value, end = decoder.raw_decode(buffer, position)
                except json.JSONDecodeError:
                    if not chunk:
                        raise
                    break
                if isinstance(value, dict):
                    rows.append(value)
                position = end

            if position > 65536:
                buffer = buffer[position:]
                position = 0

    return _columns_from_rows(rows), rows


def _preview_parquet(path: Path, *, max_rows: int) -> tuple[list[str], list[dict[str, Any]]]:
    try:
        import pyarrow.parquet as pq
    except ImportError as error:
        raise RuntimeError("Parquet preview requires pyarrow") from error

    parquet_file = pq.ParquetFile(path)
    columns = list(parquet_file.schema_arrow.names)
    batches = parquet_file.iter_batches(batch_size=max_rows)
    first_batch = next(batches, None)
    rows = first_batch.to_pylist() if first_batch is not None else []
    return columns, rows


def _columns_from_rows(rows: list[dict[str, Any]]) -> list[str]:
    return list(dict.fromkeys(key for row in rows for key in row))
