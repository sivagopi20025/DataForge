from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dataforge.scenarios.catalog import expanded_scenario_items


@dataclass
class TrainingDataValidationResult:
    path: str
    row_count: int
    errors: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not self.errors


def _jsonl_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                rows.append(json.loads(stripped))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSONL row: {exc}") from exc
    return rows


def validate_scenario_knowledge_file(path: str | Path) -> TrainingDataValidationResult:
    path = Path(path)
    rows = _jsonl_rows(path)
    scenario_ids = {item.scenario_id for item in expanded_scenario_items()}
    errors: list[str] = []
    seen: set[str] = set()
    required = {
        "scenario_id",
        "domain",
        "business_process",
        "failure_category",
        "failure_primitive",
        "validator_pattern",
        "execution_status",
        "implementation_readiness",
    }
    for index, row in enumerate(rows, 1):
        missing = sorted(required - set(row))
        if missing:
            errors.append(f"row {index}: missing fields {missing}")
        scenario_id = row.get("scenario_id")
        if scenario_id not in scenario_ids:
            errors.append(f"row {index}: unknown scenario_id {scenario_id!r}")
        if scenario_id in seen:
            errors.append(f"row {index}: duplicate scenario_id {scenario_id!r}")
        seen.add(str(scenario_id))
    if len(seen) != len(scenario_ids):
        errors.append(f"knowledge file has {len(seen)} unique scenarios; expected {len(scenario_ids)}")
    return TrainingDataValidationResult(str(path), len(rows), errors)


def validate_instruction_seed_file(path: str | Path) -> TrainingDataValidationResult:
    path = Path(path)
    rows = _jsonl_rows(path)
    scenario_ids = {item.scenario_id for item in expanded_scenario_items()}
    errors: list[str] = []
    seen_instructions: set[str] = set()
    required = {"instruction", "expected_output"}
    for index, row in enumerate(rows, 1):
        missing = sorted(required - set(row))
        if missing:
            errors.append(f"row {index}: missing fields {missing}")
            continue
        instruction = str(row["instruction"]).strip()
        if not instruction:
            errors.append(f"row {index}: blank instruction")
        normalized = instruction.lower()
        if normalized in seen_instructions:
            errors.append(f"row {index}: duplicate instruction")
        seen_instructions.add(normalized)
        output = row["expected_output"]
        if not isinstance(output, dict):
            errors.append(f"row {index}: expected_output must be an object")
            continue
        scenario_id = output.get("scenario_id")
        if scenario_id not in scenario_ids:
            errors.append(f"row {index}: unknown expected scenario_id {scenario_id!r}")
        failure_rate = output.get("failure_rate", 0.03)
        try:
            rate_value = float(failure_rate)
        except (TypeError, ValueError):
            errors.append(f"row {index}: failure_rate must be numeric")
        else:
            if not 0 <= rate_value <= 1:
                errors.append(f"row {index}: failure_rate out of range")
    return TrainingDataValidationResult(str(path), len(rows), errors)
