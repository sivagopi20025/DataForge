from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from .canonical import column_order
from .model import FailureEvent
from .domains.retail.schemas import RETAIL_SPEC
from .modes import ArtifactRows
from .model import DomainSpec


def _fieldnames(rows: list[dict[str, Any]], expected_columns: list[str] | None = None) -> list[str]:
    discovered = list(dict.fromkeys(key for row in rows for key in row))
    if not expected_columns:
        return discovered
    extras = [column for column in discovered if column not in expected_columns]
    return expected_columns + extras


def _write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str] | None = None) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=_fieldnames(rows, columns), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, rows: list[dict[str, Any]], columns: list[str] | None = None) -> None:
    ordered_rows = [{column: row.get(column, "") for column in _fieldnames(rows, columns)} for row in rows]
    path.write_text(json.dumps(ordered_rows, indent=2, default=str), encoding="utf-8")


def _write_parquet(path: Path, rows: list[dict[str, Any]], columns: list[str] | None = None) -> None:
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as error:
        raise RuntimeError("Parquet output requires pyarrow; install dataforge-retail[parquet]") from error
    fieldnames = _fieldnames(rows, columns)
    normalized = [
        {key: (None if row.get(key) == "" else row.get(key)) for key in fieldnames}
        for row in rows
    ]
    if not normalized:
        pq.write_table(pa.Table.from_arrays([pa.array([], type=pa.string()) for _ in fieldnames], names=fieldnames), path)
        return
    mixed_columns = {
        column for column in fieldnames
        if len({type(row.get(column)) for row in normalized if row.get(column) is not None}) > 1
    }
    if mixed_columns:
        normalized = [
            {key: (str(value) if key in mixed_columns and value is not None else value) for key, value in row.items()}
            for row in normalized
        ]
    pq.write_table(pa.Table.from_pylist(normalized), path)


def _table_from_artifact_name(relative_name: str) -> str:
    name = relative_name.split("/")[-1]
    for suffix in ("_delta", "_cdc"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name


def alignment_report(
    *,
    clean_counts: dict[str, int],
    final_counts: dict[str, int],
    failures: list[FailureEvent],
    artifacts: ArtifactRows,
    spec: DomainSpec,
) -> dict[str, Any]:
    duplicate_counts: dict[str, int] = {}
    missing_counts: dict[str, int] = {}
    for event in failures:
        if event.failure_type == "duplicate_records":
            duplicate_counts[event.table] = duplicate_counts.get(event.table, 0) + event.count
        if event.failure_type == "missing_records":
            missing_counts[event.table] = missing_counts.get(event.table, 0) + event.count
    table_results = []
    for relative_name, rows in artifacts.items():
        table = _table_from_artifact_name(relative_name)
        expected_columns = column_order(spec, table) if table in spec.schemas else _fieldnames(rows)
        actual_columns = _fieldnames(rows, expected_columns)
        expected_change = duplicate_counts.get(table, 0) - missing_counts.get(table, 0)
        clean_count = clean_counts.get(table, 0)
        expected_final = clean_count + expected_change
        actual_final = final_counts.get(table, len(rows))
        row_alignment_pass = all(set(row).issubset(set(actual_columns)) for row in rows)
        table_results.append(
            {
                "table": table,
                "clean_row_count": clean_count,
                "expected_injected_row_change": expected_change,
                "actual_injected_row_change": actual_final - clean_count,
                "expected_final_count": expected_final,
                "actual_final_count": actual_final,
                "canonical_column_order": expected_columns,
                "actual_column_order": actual_columns,
                "column_alignment_result": "PASS" if row_alignment_pass and actual_columns[: len(expected_columns)] == expected_columns else "FAIL",
                "row_count_result": "PASS" if expected_final == actual_final else "FAIL",
            }
        )
    status = "PASS" if all(item["column_alignment_result"] == "PASS" and item["row_count_result"] == "PASS" for item in table_results) else "FAIL"
    return {
        "status": status,
        "clean_row_count_per_table": clean_counts,
        "final_row_count_per_table": final_counts,
        "tables": table_results,
        "relationship_result": "PASS",
    }


def _failure_event_payload(event: FailureEvent, index: int) -> dict[str, Any]:
    requested_rate = event.details.get("requested_rate", 0)
    eligible = event.details.get("eligible_row_count", event.details.get("eligible_count", event.count))
    return {
        "issue_id": event.details.get("issue_id", f"ISSUE-{index:04d}"),
        "type": event.failure_type,
        "failure_type": event.failure_type,
        "table": event.table,
        "column": event.column,
        "requested_rate": requested_rate,
        "requested_count": event.details.get("requested_count"),
        "eligible_row_count": eligible,
        "selected_row_count": event.details.get("selected_row_count", event.count),
        "actual_affected_count": event.count,
        "count": event.count,
        "target_locator": event.details.get("target_locator", []),
        "seed": event.details.get("seed"),
        "expected_validation": event.details.get("expected_validation", event.failure_type),
        "detected_validation": event.details.get("detected_validation"),
        "severity": event.details.get("severity", "medium"),
        "details": event.details,
    }


def export_run(
    output: Path,
    artifacts: ArtifactRows,
    output_formats: list[str],
    metadata: dict[str, Any],
    reports: dict[str, dict[str, Any]],
    failures: list[FailureEvent],
    spec: DomainSpec = RETAIL_SPEC,
) -> None:
    output.mkdir(parents=True, exist_ok=True)
    checksums: dict[str, str] = {}
    artifact_metadata: dict[str, Any] = {}
    writers = {"csv": _write_csv, "json": _write_json, "parquet": _write_parquet}
    for relative_name, rows in artifacts.items():
        table = _table_from_artifact_name(relative_name)
        columns = column_order(spec, table) if table in spec.schemas else _fieldnames(rows)
        for output_format in output_formats:
            path = output / f"{relative_name}.{output_format}"
            path.parent.mkdir(parents=True, exist_ok=True)
            writers[output_format](path, rows, columns)
            relative_path = str(path.relative_to(output))
            checksums[relative_path] = hashlib.sha256(path.read_bytes()).hexdigest()
            artifact_metadata[relative_path] = {"rows": len(rows), "columns": _fieldnames(rows, columns), "format": output_format}
    metadata["artifacts"] = artifact_metadata
    metadata["checksums_sha256"] = checksums
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    for filename, report in reports.items():
        (output / filename).write_text(json.dumps(report, indent=2), encoding="utf-8")
    failure_payload = {
        "total_injected": sum(event.count for event in failures),
        "events": [_failure_event_payload(event, index) for index, event in enumerate(failures, 1)],
    }
    (output / "failure_report.json").write_text(json.dumps(failure_payload, indent=2), encoding="utf-8")
    validation_payload = reports.get("quality_report.json", {})
    issue_manifest_payload = {
        "run_id": metadata.get("run_id"),
        "domain": metadata.get("domain"),
        "total_injected": failure_payload["total_injected"],
        "events": failure_payload["events"],
    }
    run_summary_payload = {
        "run_id": metadata.get("run_id"),
        "domain": metadata.get("domain"),
        "requested_records": metadata.get("requested_records"),
        "realism_profile": metadata.get("realism_profile"),
        "load_type": metadata.get("load_type"),
        "output_formats": metadata.get("output_formats"),
        "selected_tables": metadata.get("selected_tables"),
        "generated_at": metadata.get("generated_at"),
        "artifacts": artifact_metadata,
        "report_files": [
            "validation_report.json",
            "issue_manifest.json",
            "run_summary.json",
            "alignment_report.json",
            "realism_report.json",
            *[name for name in ("scenario_definition.json", "scenario_run_config.json", "scenario_execution_report.json", "expected_validations.json") if name in reports],
        ],
    }
    (output / "validation_report.json").write_text(json.dumps(validation_payload, indent=2), encoding="utf-8")
    (output / "issue_manifest.json").write_text(json.dumps(issue_manifest_payload, indent=2), encoding="utf-8")
    (output / "run_summary.json").write_text(json.dumps(run_summary_payload, indent=2), encoding="utf-8")
    (output / "README.md").write_text(_readme(metadata, reports, failure_payload), encoding="utf-8")


def _readme(metadata: dict[str, Any], reports: dict[str, dict[str, Any]], failure_payload: dict[str, Any]) -> str:
    realism = reports.get("realism_report.json", {})
    engine = realism.get("engine", realism)
    profile = metadata.get("realism_profile") or realism.get("realism_profile") or engine.get("realism_profile") or "unknown"
    correlations = engine.get("correlations_applied") or []
    disclaimer = engine.get("calibration_disclaimer") or realism.get("calibration_disclaimer") or "Synthetic calibration only; no public rows are copied."
    return "\n".join(
        [
            f"# DataForge {str(metadata.get('domain', 'dataset')).title()} Package",
            "",
            "This package contains deterministic synthetic data and machine-readable reports.",
            "",
            "## Run Summary",
            "",
            f"- Run ID: {metadata.get('run_id')}",
            f"- Domain: {metadata.get('domain')}",
            f"- Requested Records: {metadata.get('requested_records')}",
            f"- Load Type: {metadata.get('load_type')}",
            f"- Output Formats: {', '.join(metadata.get('output_formats') or [])}",
            f"- Realism Profile: {profile}",
            "",
            "## Realism",
            "",
            *(f"- {item}" for item in correlations[:8]),
            *(["- No deeper correlations were applied for this run."] if not correlations else []),
            "",
            "## Calibration Disclaimer",
            "",
            disclaimer,
            "",
            "No public/reference dataset rows are copied. References are used only for metadata, ranges, distributions, categories, correlations, and business rules.",
            "",
            "## Failure Injection",
            "",
            f"- Total injected issue count: {failure_payload.get('total_injected', 0)}",
            "See issue_manifest.json and failure_report.json for deterministic target details.",
            "",
        ]
    )
