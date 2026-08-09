from __future__ import annotations

import csv
import hashlib
import io
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


GROUND_TRUTH_VERSION = "1.0"
DETECTOR_OUTPUT_VERSION = "1.0"


@dataclass(frozen=True)
class EvaluationMetrics:
    true_positive: int
    false_positive: int
    true_negative: int
    false_negative: int
    precision: float | None
    recall: float | None
    f1: float | None
    false_positive_rate: float | None
    detection_coverage: float | None

    def model_dump(self) -> dict[str, Any]:
        return self.__dict__.copy()


def stable_key(unit: str, key: dict[str, Any]) -> str:
    payload = json.dumps({"unit": unit, "key": key}, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def checksum_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def ground_truth_from_scenario_report(
    *,
    run_id: str,
    scenario_report: dict[str, Any],
    generated_at: str | None,
    candidate_universe: dict[str, set[str]],
) -> dict[str, Any]:
    failures: list[dict[str, Any]] = []
    scenario_id = scenario_report.get("scenario_id")
    failure_plan = scenario_report.get("failure_plan") or {}
    seed = failure_plan.get("seed")
    for row in scenario_report.get("ground_truth", []) or []:
        primitive_id = row.get("primitive_id")
        target = row.get("target") or {}
        table = target.get("table")
        entity_type = target.get("entity") or table or "entity"
        evaluation_unit = _evaluation_unit_for_primitive(str(primitive_id))
        key_field = _key_field_for_entity(entity_type, table)
        for index, entity_id in enumerate(row.get("affected_entities", []) or []):
            key = {key_field: str(entity_id)}
            failures.append(
                {
                    "failure_instance_id": f"{run_id}:{primitive_id}:{index}",
                    "primitive_id": primitive_id,
                    "failure_category": _failure_category_for_primitive(str(primitive_id)),
                    "evaluation_unit": evaluation_unit,
                    "evaluation_key": key,
                    "evaluation_key_hash": stable_key(evaluation_unit, key),
                    "entity_type": entity_type,
                    "table": table,
                    "entity_id": entity_id,
                    "expected_label": "failure",
                    "evidence": _compact_evidence(row.get("evidence") or {}, entity_id),
                }
            )
    return {
        "ground_truth_version": GROUND_TRUTH_VERSION,
        "run_id": run_id,
        "scenario_id": scenario_id,
        "dataset_id": run_id,
        "seed": seed,
        "generated_at": generated_at,
        "evaluation_units": _evaluation_units(candidate_universe, failures),
        "failures": failures,
    }


def ground_truth_to_jsonl(ground_truth: dict[str, Any]) -> bytes:
    lines = [json.dumps({"type": "metadata", **{k: v for k, v in ground_truth.items() if k != "failures"}}, default=str)]
    lines.extend(json.dumps({"type": "failure", **item}, default=str) for item in ground_truth.get("failures", []))
    return ("\n".join(lines) + "\n").encode("utf-8")


def ground_truth_to_csv(ground_truth: dict[str, Any]) -> bytes:
    output = io.StringIO()
    fields = ["failure_instance_id", "primitive_id", "failure_category", "evaluation_unit", "evaluation_key_hash", "table", "entity_id", "expected_label"]
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for item in ground_truth.get("failures", []):
        writer.writerow({key: item.get(key) for key in fields})
    return output.getvalue().encode("utf-8")


def dataset_manifest(
    *,
    run_id: str,
    scenario_report: dict[str, Any],
    generated_files: list[dict[str, Any]],
    table_counts: dict[str, int],
    primary_keys: dict[str, str],
    ground_truth_artifacts: dict[str, Any],
) -> dict[str, Any]:
    return {
        "manifest_version": "1.0",
        "run_id": run_id,
        "scenario_id": scenario_report.get("scenario_id"),
        "seed": (scenario_report.get("failure_plan") or {}).get("seed"),
        "failure_plan": scenario_report.get("failure_plan"),
        "tables": [
            {"name": table, "rows": table_counts.get(table, 0), "primary_key": [primary_keys.get(table, "id")]}
            for table in sorted(table_counts)
        ],
        "ground_truth_artifacts": ground_truth_artifacts,
        "generated_files": generated_files,
    }


def normalize_detector_output(payload: dict[str, Any], *, label_mapping: dict[str, str] | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    label_mapping = label_mapping or {}
    errors: list[dict[str, Any]] = []
    detections: list[dict[str, Any]] = []
    for index, row in enumerate(payload.get("detections", []) or []):
        unit = row.get("evaluation_unit")
        key = row.get("evaluation_key")
        if not unit or not isinstance(key, dict):
            errors.append({"row": index, "error": "evaluation_unit and evaluation_key are required"})
            continue
        detected = bool(row.get("predicted_failure", row.get("detected", True)))
        label = row.get("predicted_failure_type") or row.get("label") or row.get("category")
        detections.append(
            {
                "evaluation_unit": unit,
                "evaluation_key": key,
                "evaluation_key_hash": stable_key(str(unit), key),
                "predicted_failure": detected,
                "predicted_failure_type": label,
                "mapped_category": label_mapping.get(str(label), label),
                "confidence": row.get("confidence"),
            }
        )
    return detections, errors


def evaluate_detector_output(
    ground_truth: dict[str, Any],
    detector_payload: dict[str, Any],
    *,
    label_mapping: dict[str, str] | None = None,
) -> dict[str, Any]:
    detections, import_errors = normalize_detector_output(detector_payload, label_mapping=label_mapping)
    truth_hashes = {item["evaluation_key_hash"]: item for item in ground_truth.get("failures", [])}
    candidate_hashes = _candidate_hashes(ground_truth)
    detected_hashes = {item["evaluation_key_hash"] for item in detections if item["predicted_failure"]}
    known_detector_hashes = detected_hashes & candidate_hashes
    unknown_detector_hashes = detected_hashes - candidate_hashes

    tp_hashes = known_detector_hashes & set(truth_hashes)
    fp_hashes = known_detector_hashes - set(truth_hashes)
    fn_hashes = set(truth_hashes) - known_detector_hashes
    tn = max(0, len(candidate_hashes - set(truth_hashes) - fp_hashes))
    metrics = _metrics(len(tp_hashes), len(fp_hashes), tn, len(fn_hashes))
    per_failure = _per_failure_metrics(ground_truth, known_detector_hashes, candidate_hashes)
    return {
        "detector_output_version": DETECTOR_OUTPUT_VERSION,
        "detector_name": detector_payload.get("detector_name", "unknown-detector"),
        "detector_version": detector_payload.get("detector_version"),
        "run_id": ground_truth.get("run_id"),
        "import_errors": import_errors,
        "unknown_detections": [{"evaluation_key_hash": value} for value in sorted(unknown_detector_hashes)[:100]],
        "metrics": metrics.model_dump(),
        "per_failure_metrics": per_failure,
        "false_negative_examples": [truth_hashes[value] for value in sorted(fn_hashes)[:25]],
        "false_positive_examples": [item for item in detections if item["evaluation_key_hash"] in fp_hashes][:25],
        "micro_average": metrics.model_dump(),
        "macro_average": _macro_average(per_failure),
    }


def acceptance_status(metrics: dict[str, Any], thresholds: dict[str, float] | None) -> dict[str, Any]:
    thresholds = thresholds or {}
    failures = []
    for key, threshold in thresholds.items():
        metric_key = key.replace("minimum_", "")
        value = metrics.get(metric_key)
        if value is None:
            failures.append({"threshold": key, "reason": "metric undefined"})
        elif float(value) < float(threshold):
            failures.append({"threshold": key, "required": threshold, "actual": value})
    return {"status": "PASS" if not failures else "FAIL", "failures": failures}


def detector_payload_from_jsonl(text: str) -> dict[str, Any]:
    detections = []
    metadata: dict[str, Any] = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("type") == "metadata":
            metadata.update(row)
        else:
            detections.append(row)
    return {"detector_name": metadata.get("detector_name", "jsonl-detector"), "detector_version": metadata.get("detector_version"), "detections": detections}


def detector_payload_from_csv(text: str) -> dict[str, Any]:
    rows = list(csv.DictReader(io.StringIO(text)))
    detections = []
    for row in rows:
        key = {k.replace("key_", ""): v for k, v in row.items() if k.startswith("key_") and v}
        detections.append(
            {
                "evaluation_unit": row.get("evaluation_unit"),
                "evaluation_key": key,
                "predicted_failure": str(row.get("predicted_failure", "true")).lower() in {"true", "1", "yes"},
                "predicted_failure_type": row.get("predicted_failure_type"),
                "confidence": float(row["confidence"]) if row.get("confidence") else None,
            }
        )
    return {"detector_name": "csv-detector", "detections": detections}


def _metrics(tp: int, fp: int, tn: int, fn: int) -> EvaluationMetrics:
    precision = _safe_div(tp, tp + fp)
    recall = _safe_div(tp, tp + fn)
    f1 = None if precision is None or recall is None or precision + recall == 0 else round(2 * precision * recall / (precision + recall), 6)
    return EvaluationMetrics(
        true_positive=tp,
        false_positive=fp,
        true_negative=tn,
        false_negative=fn,
        precision=precision,
        recall=recall,
        f1=f1,
        false_positive_rate=_safe_div(fp, fp + tn),
        detection_coverage=_safe_div(tp, tp + fn),
    )


def _safe_div(left: int, right: int) -> float | None:
    return None if right == 0 else round(left / right, 6)


def _candidate_hashes(ground_truth: dict[str, Any]) -> set[str]:
    hashes: set[str] = set()
    for unit in ground_truth.get("evaluation_units", []):
        hashes.update(unit.get("candidate_key_hashes", []))
    hashes.update(item["evaluation_key_hash"] for item in ground_truth.get("failures", []))
    return hashes


def _per_failure_metrics(ground_truth: dict[str, Any], detected_hashes: set[str], candidate_hashes: set[str]) -> list[dict[str, Any]]:
    by_primitive: dict[str, set[str]] = {}
    for item in ground_truth.get("failures", []):
        by_primitive.setdefault(str(item["primitive_id"]), set()).add(item["evaluation_key_hash"])
    rows = []
    for primitive, truth in sorted(by_primitive.items()):
        tp = len(truth & detected_hashes)
        fn = len(truth - detected_hashes)
        # FP is reported overall; per-primitive customer label mapping can refine this later.
        rows.append({"primitive_id": primitive, **_metrics(tp, 0, max(0, len(candidate_hashes - truth)), fn).model_dump()})
    return rows


def _macro_average(rows: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for metric in ("precision", "recall", "f1"):
        values = [row[metric] for row in rows if row.get(metric) is not None]
        result[metric] = round(sum(values) / len(values), 6) if values else None
    return result


def _evaluation_unit_for_primitive(primitive_id: str) -> str:
    if "aggregate" in primitive_id:
        return "group"
    if "volume" in primitive_id:
        return "time_window"
    if "cross_table" in primitive_id:
        return "relationship"
    return "entity"


def _key_field_for_entity(entity_type: str, table: str | None) -> str:
    if table and table.endswith("ies"):
        return f"{table[:-3]}y_id"
    if table and table.endswith("s"):
        return f"{table[:-1]}_id"
    return f"{entity_type}_id"


def _failure_category_for_primitive(primitive_id: str) -> str:
    if "duplicate" in primitive_id or "retry" in primitive_id:
        return "duplication"
    if "sla" in primitive_id or "timeout" in primitive_id or "timestamp" in primitive_id:
        return "sla_violation"
    if "aggregate" in primitive_id or "cross_table" in primitive_id:
        return "reconciliation"
    if "threshold" in primitive_id or "negative" in primitive_id:
        return "threshold_violation"
    return primitive_id


def _compact_evidence(evidence: dict[str, Any], entity_id: Any) -> dict[str, Any]:
    compact = {key: value for key, value in evidence.items() if key not in {"violations", "comparisons", "groups", "transitions", "anomalies"}}
    for key in ("violations", "comparisons", "groups", "transitions", "anomalies"):
        values = evidence.get(key)
        if isinstance(values, list):
            compact[key] = values[:3]
    compact["entity_id"] = entity_id
    return compact


def _evaluation_units(candidate_universe: dict[str, set[str]], failures: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for table, ids in sorted(candidate_universe.items()):
        unit = "entity"
        key_field = _key_field_for_entity(table, table)
        candidate_keys = [{key_field: value} for value in sorted(ids)]
        rows.append(
            {
                "evaluation_unit": unit,
                "table": table,
                "candidate_count": len(ids),
                "candidate_keys": candidate_keys,
                "candidate_key_hashes": [stable_key(unit, key) for key in candidate_keys],
            }
        )
    if not rows:
        rows.append(
            {
                "evaluation_unit": "entity",
                "table": None,
                "candidate_count": len(failures),
                "candidate_keys": [item["evaluation_key"] for item in failures],
                "candidate_key_hashes": [item["evaluation_key_hash"] for item in failures],
            }
        )
    return rows
