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


def quality_score(checks: list[dict[str, Any]]) -> int:
    if not checks:
        return 100
    score = 0
    for category, weight in SCORING_WEIGHTS.items():
        category_checks = [check for check in checks if check_category(check) == category]
        if not category_checks or all(check.get("status") == "PASS" for check in category_checks):
            score += weight
    return score


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
    score = quality_score(normalized)
    issues = [
        {"type": check["name"], "count": int(check.get("failures", 1) or 1)}
        for check in normalized
        if check["status"] == "FAIL"
    ]
    status = "PASS" if score >= 80 else "FAIL"
    if failed and score == 100:
        status = "FAIL"
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
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(),
    }
    return report
