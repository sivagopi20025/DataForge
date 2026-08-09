from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .model import Dataset, DomainSpec


SCORING_WEIGHTS = {
    "pk": 25,
    "fk": 20,
    "schema": 20,
    "business": 15,
    "duplicates": 10,
    "date": 10,
}

TABLE_LEVEL_CHECKS = {
    "schema_columns_match",
    "schema_column_order",
    "schema_datatype_match",
    "schema_renamed_column_suspected",
    "schema_nullability",
    "table_has_rows",
}


def check_category(check: dict[str, Any]) -> str:
    name = str(check.get("name", check.get("check", "")))
    if name in {"primary_key_unique"}:
        return "pk"
    if name in {"referential_integrity"}:
        return "fk"
    if name in {
        "schema_columns_match",
        "schema_column_order",
        "schema_datatype_match",
        "schema_renamed_column_suspected",
        "schema_nullability",
        "table_has_rows",
    }:
        return "schema"
    if "duplicate" in name:
        return "duplicates"
    if "date" in name or "datetime" in name:
        return "date"
    if name in {"not_null", "consistent_datatype", "numeric_type", "non_negative", "outlier_threshold"}:
        return "schema"
    return "business"


def quality_score(checks: list[dict[str, Any]], data: Dataset | None = None) -> int:
    return quality_score_details(checks, data=data)["score"]


def quality_score_details(checks: list[dict[str, Any]], data: Dataset | None = None) -> dict[str, Any]:
    if not checks:
        return {"score": 100, "categories": {}}
    categories: dict[str, dict[str, Any]] = {}
    for category, weight in SCORING_WEIGHTS.items():
        category_checks = [check for check in checks if check_category(check) == category]
        if not category_checks:
            categories[category] = {
                "weight": weight,
                "score": weight,
                "health": 1.0,
                "failed_checks": 0,
                "total_checks": 0,
                "impact": 0.0,
            }
            continue
        impacts = [_check_impact(check, data) for check in category_checks]
        average_impact = min(1.0, sum(impacts) / len(impacts))
        category_score = round(weight * (1.0 - average_impact), 2)
        categories[category] = {
            "weight": weight,
            "score": category_score,
            "health": round(1.0 - average_impact, 4),
            "failed_checks": sum(1 for check in category_checks if check.get("status") != "PASS"),
            "total_checks": len(category_checks),
            "impact": round(average_impact, 4),
        }
    score = int(sum(item["score"] for item in categories.values()))
    if any(check.get("status") != "PASS" for check in checks) and score >= 100:
        score = 99
    return {"score": max(0, min(100, score)), "categories": categories}


def _check_impact(check: dict[str, Any], data: Dataset | None = None) -> float:
    if check.get("status") == "PASS":
        return 0.0
    name = str(check.get("name", check.get("check", "")))
    failures = _safe_int(check.get("failures", 1), default=1)
    if failures <= 0:
        return 0.0
    if name in TABLE_LEVEL_CHECKS:
        return 1.0
    denominator = _check_denominator(check, data)
    if denominator <= 0:
        return 1.0
    return max(0.0, min(1.0, failures / denominator))


def _check_denominator(check: dict[str, Any], data: Dataset | None = None) -> int:
    table = check.get("table")
    if data and isinstance(table, str) and table in data:
        return max(1, len(data.get(table, [])))
    expected = check.get("expected")
    actual = check.get("actual")
    for value in (expected, actual):
        parsed = _safe_int(value, default=-1)
        if parsed > 0:
            return parsed
    return max(1, _safe_int(check.get("failures", 1), default=1))


def _safe_int(value: Any, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def standardize_check(check: dict[str, Any]) -> dict[str, Any]:
    name = str(check.get("name", check.get("check", "validation")))
    failures = int(check.get("failures", 0))
    expected = check.get("expected", check.get("expected_type", "valid"))
    actual = check.get("actual", failures)
    return {
        **check,
        "name": name,
        "check": name,
        "status": str(check.get("status", "PASS" if failures == 0 else "FAIL")),
        "expected": str(expected),
        "actual": str(actual),
    }


def build_validation_report(
    *,
    checks: list[dict[str, Any]],
    data: Dataset,
    spec: DomainSpec,
    run_id: str = "",
    load_type: str = "",
    file_format: str = "",
    record_count: int | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    normalized = [standardize_check(check) for check in checks]
    passed = sum(1 for check in normalized if check["status"] == "PASS")
    failed = len(normalized) - passed
    score_details = quality_score_details(normalized, data=data)
    score = score_details["score"]
    issues = [
        {"type": check["name"], "count": int(check.get("failures", 1) or 1)}
        for check in normalized
        if check["status"] == "FAIL"
    ]
    status = "PASS" if failed == 0 and score >= 80 else "FAIL"
    report = {
        "run_id": run_id,
        "domain": spec.name,
        "load_type": load_type,
        "format": file_format,
        "record_count": record_count if record_count is not None else sum(len(rows) for rows in data.values()),
        "quality_score": score,
        "status": status,
        "overall_status": status,
        "summary": {"total_checks": len(normalized), "passed": passed, "failed": failed},
        "issues": issues,
        "checks": normalized,
        "scoring": score_details,
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(),
    }
    return report
