from __future__ import annotations

import copy
import math
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Callable

from dataforge.model import Dataset, DomainSpec, FailureEvent


@dataclass(frozen=True)
class PrimitiveDefinition:
    primitive_id: str
    description: str
    runtime_status: str
    executor: Callable[["PrimitiveExecutionContext"], "PrimitiveResult"] | None = None
    aliases: tuple[str, ...] = ()


@dataclass
class PrimitiveExecutionContext:
    dataset: Dataset
    spec: DomainSpec
    parameters: dict[str, Any]
    seed: int = 42
    severity: str = "medium"


@dataclass
class PrimitiveResult:
    primitive_id: str
    dataset: Dataset
    selected_count: int
    actual_mutated_count: int
    affected_tables: list[str]
    affected_entity_ids: list[Any]
    mutation_metadata: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def to_failure_event(self, table: str, column: str | None = None) -> FailureEvent:
        return FailureEvent(
            self.primitive_id,
            table,
            column,
            self.actual_mutated_count,
            {
                "requested_rate": self.mutation_metadata.get("affected_rate_default", self.mutation_metadata.get("affected_rate", 0.03)),
                "eligible_row_count": self.mutation_metadata.get("eligible_row_count", self.selected_count),
                "selected_row_count": self.selected_count,
                "actual_affected_count": self.actual_mutated_count,
                "target_locator": self.affected_entity_ids,
                "seed": self.mutation_metadata.get("seed"),
                "severity": self.mutation_metadata.get("severity", "medium"),
                "primitive_id": self.primitive_id,
                **self.mutation_metadata,
            },
        )


class PrimitiveRegistry:
    def __init__(self) -> None:
        self._definitions: dict[str, PrimitiveDefinition] = {}
        self._aliases: dict[str, str] = {}

    def register(self, definition: PrimitiveDefinition) -> None:
        self._definitions[definition.primitive_id] = definition
        for alias in definition.aliases:
            self._aliases[alias] = definition.primitive_id

    def resolve_id(self, primitive_id: str) -> str:
        return self._aliases.get(primitive_id, primitive_id)

    def get(self, primitive_id: str) -> PrimitiveDefinition:
        canonical = self.resolve_id(primitive_id)
        if canonical not in self._definitions:
            raise KeyError(f"Unknown failure primitive: {primitive_id}")
        return self._definitions[canonical]

    def runtime_implemented(self) -> set[str]:
        return {key for key, definition in self._definitions.items() if definition.executor and definition.runtime_status in {"runtime_implemented", "runtime_partial"}}

    def metadata_only(self) -> set[str]:
        return {key for key, definition in self._definitions.items() if not definition.executor or definition.runtime_status == "metadata_only"}

    def execute(self, primitive_id: str, context: PrimitiveExecutionContext) -> PrimitiveResult:
        definition = self.get(primitive_id)
        if not definition.executor:
            raise NotImplementedError(f"Primitive {primitive_id} is {definition.runtime_status} and cannot execute yet")
        return definition.executor(context)


def _table_and_rows(context: PrimitiveExecutionContext) -> tuple[str, list[dict[str, Any]], str]:
    table = str(context.parameters.get("table") or context.parameters.get("primary_table") or "")
    if table not in context.dataset:
        raise ValueError(f"Primitive table is missing from dataset: {table}")
    schema = context.spec.schemas.get(table)
    id_column = str(context.parameters.get("id_column") or (schema.primary_key if schema else "id"))
    return table, context.dataset[table], id_column


def _target_indices(rows: list[dict[str, Any]], seed: int, rate: float) -> list[int]:
    if not rows or rate <= 0:
        return []
    rng = random.Random(seed + 3109)
    count = max(1, int(len(rows) * min(rate, 0.10)))
    return sorted(rng.sample(range(len(rows)), min(count, len(rows))))


def _rate(context: PrimitiveExecutionContext) -> float:
    return float(context.parameters.get("affected_rate", context.parameters.get("affected_rate_default", 0.03)))


def _column(context: PrimitiveExecutionContext, rows: list[dict[str, Any]], fallback: str | None = None) -> str:
    column = context.parameters.get("column")
    if isinstance(column, str) and rows and column in rows[0]:
        return column
    columns = context.parameters.get("columns")
    if isinstance(columns, list):
        for item in columns:
            if isinstance(item, str) and rows and item in rows[0]:
                return item
    if fallback and rows and fallback in rows[0]:
        return fallback
    if rows:
        for key in rows[0]:
            if not key.endswith("_id"):
                return key
        return next(iter(rows[0]))
    return fallback or "value"


def _temporal_column(context: PrimitiveExecutionContext, rows: list[dict[str, Any]], fallback: str | None = None) -> str:
    preferred_names = (
        "timestamp",
        "event_time",
        "event_timestamp",
        "created_at",
        "updated_at",
        "date",
        "time",
        "submitted",
        "settled",
        "shipped",
        "delivered",
        "payment_date",
        "order_date",
        "visit_date",
        "position_date",
        "due_date",
    )
    explicit = context.parameters.get("column")
    if isinstance(explicit, str) and rows and explicit in rows[0]:
        return explicit
    for column in context.parameters.get("columns", []):
        if isinstance(column, str) and rows and column in rows[0] and any(name in column.lower() for name in preferred_names):
            return column
    if rows:
        for column in rows[0]:
            if any(name in column.lower() for name in preferred_names):
                return column
    return _column(context, rows, fallback)


def _sequence_column(context: PrimitiveExecutionContext, rows: list[dict[str, Any]], fallback: str | None = None) -> str:
    preferred_names = ("sequence", "seq", "number", "position", "status", "id")
    explicit = context.parameters.get("column")
    if isinstance(explicit, str) and rows and explicit in rows[0]:
        return explicit
    for column in context.parameters.get("columns", []):
        if isinstance(column, str) and rows and column in rows[0] and any(name in column.lower() for name in preferred_names):
            return column
    if rows:
        for column in rows[0]:
            if any(name in column.lower() for name in preferred_names):
                return column
    return _column(context, rows, fallback)


def _result(context: PrimitiveExecutionContext, primitive_id: str, table: str, rows: list[dict[str, Any]], id_column: str, indices: list[int], column: str | None = None, warnings: list[str] | None = None) -> PrimitiveResult:
    return PrimitiveResult(
        primitive_id=primitive_id,
        dataset=context.dataset,
        selected_count=len(indices),
        actual_mutated_count=len(indices),
        affected_tables=[table],
        affected_entity_ids=[rows[index].get(id_column) for index in indices if index < len(rows)],
        mutation_metadata={
            "table": table,
            "column": column,
            "id_column": id_column,
            "eligible_row_count": len(rows),
            "affected_rate_default": _rate(context),
            "seed": context.seed,
            "severity": context.severity,
        },
        warnings=warnings or [],
    )


def duplicate_entity(context: PrimitiveExecutionContext) -> PrimitiveResult:
    table, rows, id_column = _table_and_rows(context)
    indices = _target_indices(rows, context.seed, _rate(context))
    originals = [copy.deepcopy(rows[index]) for index in indices]
    rows.extend(originals)
    result = _result(context, "duplicate_entity", table, rows, id_column, indices, id_column)
    result.actual_mutated_count = len(originals)
    return result


def null_required_attribute(context: PrimitiveExecutionContext) -> PrimitiveResult:
    table, rows, id_column = _table_and_rows(context)
    indices = _target_indices(rows, context.seed, _rate(context))
    column = _column(context, rows)
    for index in indices:
        rows[index][column] = ""
    return _result(context, "null_required_attribute", table, rows, id_column, indices, column)


def invalid_reference(context: PrimitiveExecutionContext) -> PrimitiveResult:
    table, rows, id_column = _table_and_rows(context)
    schema = context.spec.schemas[table]
    fallback = schema.foreign_keys[0].column if schema.foreign_keys else id_column
    column = _column(context, rows, fallback)
    indices = _target_indices(rows, context.seed, _rate(context))
    for offset, index in enumerate(indices, 1):
        rows[index][column] = f"DF-MISSING-{context.seed}-{offset:04d}"
    return _result(context, "invalid_reference", table, rows, id_column, indices, column)


def invalid_datatype(context: PrimitiveExecutionContext) -> PrimitiveResult:
    table, rows, id_column = _table_and_rows(context)
    column = _column(context, rows)
    indices = _target_indices(rows, context.seed, _rate(context))
    for index in indices:
        rows[index][column] = "DF_INVALID_TYPE"
    return _result(context, "invalid_datatype", table, rows, id_column, indices, column)


def negative_numeric_value(context: PrimitiveExecutionContext) -> PrimitiveResult:
    table, rows, id_column = _table_and_rows(context)
    column = _column(context, rows, context.spec.numeric_columns.get(table))
    indices = _target_indices(rows, context.seed, _rate(context))
    for index in indices:
        rows[index][column] = -500
    return _result(context, "negative_numeric_value", table, rows, id_column, indices, column)


def value_above_threshold(context: PrimitiveExecutionContext) -> PrimitiveResult:
    table, rows, id_column = _table_and_rows(context)
    column = _column(context, rows, context.spec.numeric_columns.get(table))
    indices = _target_indices(rows, context.seed, _rate(context))
    threshold = Decimal(str(context.parameters.get("threshold", "1000000")))
    for index in indices:
        rows[index][column] = str(threshold + Decimal("999"))
    return _result(context, "value_above_threshold", table, rows, id_column, indices, column)


def future_timestamp(context: PrimitiveExecutionContext) -> PrimitiveResult:
    table, rows, id_column = _table_and_rows(context)
    column = _column(context, rows, context.spec.date_columns.get(table))
    indices = _target_indices(rows, context.seed, _rate(context))
    for index in indices:
        rows[index][column] = "2035-15-99"
    return _result(context, "future_timestamp", table, rows, id_column, indices, column)


def missing_entity(context: PrimitiveExecutionContext) -> PrimitiveResult:
    table, rows, id_column = _table_and_rows(context)
    original_rows = list(rows)
    indices = _target_indices(rows, context.seed, _rate(context))
    affected = [rows[index].get(id_column) for index in indices]
    for index in sorted(indices, reverse=True):
        rows.pop(index)
    result = PrimitiveResult(
        primitive_id="missing_entity",
        dataset=context.dataset,
        selected_count=len(indices),
        actual_mutated_count=len(indices),
        affected_tables=[table],
        affected_entity_ids=affected,
        mutation_metadata={
            "table": table,
            "id_column": id_column,
            "eligible_row_count": len(original_rows),
            "affected_rate_default": _rate(context),
            "seed": context.seed,
            "severity": context.severity,
        },
    )
    return result


def timestamp_delay(context: PrimitiveExecutionContext) -> PrimitiveResult:
    table, rows, id_column = _table_and_rows(context)
    column = _temporal_column(context, rows, context.spec.date_columns.get(table))
    indices = _target_indices(rows, context.seed, _rate(context))
    baseline_rows = context.dataset.setdefault("__df_sla_baseline", [])
    for offset, index in enumerate(indices, 1):
        row = rows[index]
        original_value = row.get(column)
        try:
            rows[index][column] = (datetime.fromisoformat(str(original_value)) + timedelta(days=7)).isoformat()
        except (TypeError, ValueError):
            rows[index][column] = "2035-01-01T00:00:00"
        baseline_rows.append(
            {
                "baseline_id": f"SLA-DLY-{context.seed}-{offset:04d}",
                "sla_type": "duration",
                "table": table,
                "id_column": id_column,
                "entity_id": row.get(id_column),
                "pk_column": context.spec.schemas[table].primary_key if table in context.spec.schemas else id_column,
                "pk_value": row.get(context.spec.schemas[table].primary_key) if table in context.spec.schemas else row.get(id_column),
                "start_time": original_value,
                "end_column": column,
                "allowed_seconds": 86400,
            }
        )
    result = _result(context, "timestamp_delay", table, rows, id_column, indices, column)
    result.mutation_metadata["baseline_table"] = "__df_sla_baseline"
    result.mutation_metadata["sla_mode"] = "duration"
    return result


def timestamp_out_of_order(context: PrimitiveExecutionContext) -> PrimitiveResult:
    table, rows, id_column = _table_and_rows(context)
    column = _temporal_column(context, rows, context.spec.date_columns.get(table))
    indices = _target_indices(rows, context.seed, _rate(context))
    for offset, index in enumerate(indices, 1):
        rows[index][column] = f"1900-01-{min(offset, 28):02d}T00:00:00"
    result = _result(context, "timestamp_out_of_order", table, rows, id_column, indices, column)
    result.mutation_metadata["sequence_issue_type"] = "timestamp_out_of_order"
    return result


def sequence_gap(context: PrimitiveExecutionContext) -> PrimitiveResult:
    table, rows, id_column = _table_and_rows(context)
    column = _sequence_column(context, rows, id_column)
    indices = _target_indices(rows, context.seed, _rate(context))
    for offset, index in enumerate(indices, 1):
        rows[index][column] = f"DF_SEQUENCE_GAP_{context.seed}_{offset:04d}"
    result = _result(context, "sequence_gap", table, rows, id_column, indices, column)
    result.mutation_metadata["sequence_issue_type"] = "sequence_gap"
    return result


def duplicate_event(context: PrimitiveExecutionContext) -> PrimitiveResult:
    result = duplicate_entity(context)
    result.primitive_id = "duplicate_event"
    result.mutation_metadata["sequence_issue_type"] = "duplicate_event"
    return result


def calculation_error(context: PrimitiveExecutionContext) -> PrimitiveResult:
    table, rows, id_column = _table_and_rows(context)
    column = _column(context, rows, context.spec.numeric_columns.get(table))
    indices = _target_indices(rows, context.seed, _rate(context))
    for index in indices:
        try:
            rows[index][column] = str(Decimal(str(rows[index].get(column, 0))) + Decimal("123.45"))
        except (InvalidOperation, TypeError):
            rows[index][column] = "123.45"
    return _result(context, "calculation_error", table, rows, id_column, indices, column)


def capacity_exceeded(context: PrimitiveExecutionContext) -> PrimitiveResult:
    return value_above_threshold(context)


def _numeric_delta(value: Any, delta: Decimal = Decimal("17.25")) -> Any:
    try:
        return str(Decimal(str(value)) + delta)
    except (InvalidOperation, TypeError):
        return f"DF_MISMATCH_{value}"


def _mismatch_column(context: PrimitiveExecutionContext, rows: list[dict[str, Any]]) -> str:
    numeric = context.spec.numeric_columns.get(str(context.parameters.get("table") or ""))
    if numeric and rows and numeric in rows[0]:
        return numeric
    return _column(context, rows)


def cross_table_mismatch(context: PrimitiveExecutionContext) -> PrimitiveResult:
    table, rows, id_column = _table_and_rows(context)
    if not rows:
        raise ValueError("cross_table_mismatch requires at least one candidate row")
    column = _mismatch_column(context, rows)
    indices = _target_indices(rows, context.seed, _rate(context))
    baseline_table = "__df_cross_table_baseline"
    baseline_rows = context.dataset.setdefault(baseline_table, [])
    baseline_ids: list[Any] = []
    changed_fields: list[dict[str, Any]] = []
    for offset, index in enumerate(indices, 1):
        row = rows[index]
        entity_id = row.get(id_column)
        original_value = row.get(column)
        baseline_id = f"XTB-{context.seed}-{offset:04d}"
        baseline_rows.append(
            {
                "baseline_id": baseline_id,
                "source_table": table,
                "source_id_column": id_column,
                "source_entity_id": entity_id,
                "source_pk_column": context.spec.schemas[table].primary_key if table in context.spec.schemas else id_column,
                "source_pk_value": row.get(context.spec.schemas[table].primary_key) if table in context.spec.schemas else entity_id,
                "source_column": column,
                "expected_value": original_value,
            }
        )
        row[column] = _numeric_delta(original_value)
        baseline_ids.append(baseline_id)
        changed_fields.append(
            {
                "entity_id": entity_id,
                "column": column,
                "expected_value": original_value,
                "actual_value": row[column],
            }
        )
    result = _result(context, "cross_table_mismatch", table, rows, id_column, indices, column)
    result.mutation_metadata.update(
        {
            "baseline_table": baseline_table,
            "baseline_ids": baseline_ids,
            "comparison_rule": "current_value_equals_expected_baseline",
            "changed_fields": changed_fields[:100],
            "count_semantics": "entity_level",
        }
    )
    return result


def aggregate_mismatch(context: PrimitiveExecutionContext) -> PrimitiveResult:
    table, rows, id_column = _table_and_rows(context)
    if not rows:
        raise ValueError("aggregate_mismatch requires at least one candidate row")
    value_column = _mismatch_column(context, rows)
    group_column = str(context.parameters.get("group_key") or context.parameters.get("group_keys", [id_column])[0] if isinstance(context.parameters.get("group_keys"), list) and context.parameters.get("group_keys") else context.parameters.get("group_key") or id_column)
    if group_column not in rows[0]:
        raise ValueError(f"aggregate_mismatch group column is missing: {group_column}")
    candidate_groups = list(dict.fromkeys(row.get(group_column) for row in rows))
    selected_indices = _target_indices([{"group": group} for group in candidate_groups], context.seed, _rate(context))
    selected_groups = [candidate_groups[index] for index in selected_indices]
    baseline_table = "__df_aggregate_baseline"
    baseline_rows = context.dataset.setdefault(baseline_table, [])
    changed_fields: list[dict[str, Any]] = []
    affected_ids: list[Any] = []
    for offset, group_value in enumerate(selected_groups, 1):
        group_rows = [row for row in rows if row.get(group_column) == group_value]
        try:
            expected_total = sum(Decimal(str(row.get(value_column, 0))) for row in group_rows)
        except (InvalidOperation, TypeError):
            expected_total = Decimal(len(group_rows))
        baseline_rows.append(
            {
                "baseline_id": f"AGG-{context.seed}-{offset:04d}",
                "detail_table": table,
                "aggregate_table": table,
                "group_key": group_column,
                "group_value": group_value,
                "detail_value_column": value_column,
                "expected_aggregate": str(expected_total),
                "aggregation_function": "sum",
            }
        )
        if group_rows:
            target = group_rows[0]
            target[value_column] = _numeric_delta(target.get(value_column), Decimal("23.50"))
            affected_ids.append(target.get(id_column))
            changed_fields.append({"group_id": group_value, "column": value_column, "expected_aggregate": str(expected_total)})
    result = PrimitiveResult(
        primitive_id="aggregate_mismatch",
        dataset=context.dataset,
        selected_count=len(selected_groups),
        actual_mutated_count=len(selected_groups),
        affected_tables=[table],
        affected_entity_ids=affected_ids,
        mutation_metadata={
            "table": table,
            "id_column": id_column,
            "group_key": group_column,
            "value_column": value_column,
            "eligible_row_count": len(candidate_groups),
            "affected_rate_default": _rate(context),
            "seed": context.seed,
            "severity": context.severity,
            "baseline_table": baseline_table,
            "changed_fields": changed_fields[:100],
            "count_semantics": "group_level",
        },
    )
    return result


def _status_column(context: PrimitiveExecutionContext, rows: list[dict[str, Any]]) -> str:
    explicit = context.parameters.get("status_column") or context.parameters.get("column")
    if isinstance(explicit, str) and rows and explicit in rows[0]:
        return explicit
    for column in context.parameters.get("columns", []):
        if isinstance(column, str) and rows and column in rows[0] and ("status" in column.lower() or "state" in column.lower()):
            return column
    if rows:
        for column in rows[0]:
            if "status" in column.lower() or "state" in column.lower():
                return column
    return _column(context, rows)


def invalid_state_transition(context: PrimitiveExecutionContext) -> PrimitiveResult:
    table, rows, id_column = _table_and_rows(context)
    if not rows:
        raise ValueError("invalid_state_transition requires at least one candidate row")
    column = _status_column(context, rows)
    indices = _target_indices(rows, context.seed, _rate(context))
    baseline_rows = context.dataset.setdefault("__df_state_transition_baseline", [])
    changed_fields: list[dict[str, Any]] = []
    for offset, index in enumerate(indices, 1):
        row = rows[index]
        old_state = row.get(column)
        new_state = f"DF_INVALID_STATE_{context.seed}_{offset:04d}"
        baseline_rows.append(
            {
                "baseline_id": f"STM-{context.seed}-{offset:04d}",
                "table": table,
                "id_column": id_column,
                "entity_id": row.get(id_column),
                "pk_column": context.spec.schemas[table].primary_key if table in context.spec.schemas else id_column,
                "pk_value": row.get(context.spec.schemas[table].primary_key) if table in context.spec.schemas else row.get(id_column),
                "status_column": column,
                "previous_state": old_state,
                "allowed_states": [old_state],
                "violated_rule": "impossible_transition",
            }
        )
        row[column] = new_state
        changed_fields.append({"entity_id": row.get(id_column), "previous_state": old_state, "current_state": new_state, "status_column": column})
    result = _result(context, "invalid_state_transition", table, rows, id_column, indices, column)
    result.mutation_metadata.update({"baseline_table": "__df_state_transition_baseline", "changed_fields": changed_fields[:100], "count_semantics": "entity_level"})
    return result


def stale_timestamp(context: PrimitiveExecutionContext) -> PrimitiveResult:
    table, rows, id_column = _table_and_rows(context)
    if not rows:
        raise ValueError("stale_timestamp requires at least one candidate row")
    column = _temporal_column(context, rows, context.spec.date_columns.get(table))
    indices = _target_indices(rows, context.seed, _rate(context))
    reference_time = str(context.parameters.get("reference_time", "2026-01-01T00:00:00"))
    allowed_seconds = int(context.parameters.get("allowed_seconds", 86400))
    stale_value = "2000-01-01T00:00:00"
    baseline_rows = context.dataset.setdefault("__df_sla_baseline", [])
    for offset, index in enumerate(indices, 1):
        row = rows[index]
        baseline_rows.append(
            {
                "baseline_id": f"SLA-AGE-{context.seed}-{offset:04d}",
                "sla_type": "age",
                "table": table,
                "id_column": id_column,
                "entity_id": row.get(id_column),
                "pk_column": context.spec.schemas[table].primary_key if table in context.spec.schemas else id_column,
                "pk_value": row.get(context.spec.schemas[table].primary_key) if table in context.spec.schemas else row.get(id_column),
                "timestamp_column": column,
                "reference_time": reference_time,
                "allowed_seconds": allowed_seconds,
            }
        )
        row[column] = stale_value
    result = _result(context, "stale_timestamp", table, rows, id_column, indices, column)
    result.mutation_metadata.update({"baseline_table": "__df_sla_baseline", "sla_mode": "age", "reference_time": reference_time, "allowed_seconds": allowed_seconds})
    return result


def timeout_violation(context: PrimitiveExecutionContext) -> PrimitiveResult:
    table, rows, id_column = _table_and_rows(context)
    if not rows:
        raise ValueError("timeout_violation requires at least one candidate row")
    column = _temporal_column(context, rows, context.spec.date_columns.get(table))
    indices = _target_indices(rows, context.seed, _rate(context))
    start_time = str(context.parameters.get("start_time", "2026-01-01T00:00:00"))
    allowed_seconds = int(context.parameters.get("allowed_seconds", 86400))
    end_time = (datetime.fromisoformat(start_time) + timedelta(seconds=allowed_seconds + 7200)).isoformat()
    baseline_rows = context.dataset.setdefault("__df_sla_baseline", [])
    for offset, index in enumerate(indices, 1):
        row = rows[index]
        baseline_rows.append(
            {
                "baseline_id": f"SLA-TMO-{context.seed}-{offset:04d}",
                "sla_type": "duration",
                "table": table,
                "id_column": id_column,
                "entity_id": row.get(id_column),
                "pk_column": context.spec.schemas[table].primary_key if table in context.spec.schemas else id_column,
                "pk_value": row.get(context.spec.schemas[table].primary_key) if table in context.spec.schemas else row.get(id_column),
                "start_time": start_time,
                "end_column": column,
                "allowed_seconds": allowed_seconds,
            }
        )
        row[column] = end_time
    result = _result(context, "timeout_violation", table, rows, id_column, indices, column)
    result.mutation_metadata.update({"baseline_table": "__df_sla_baseline", "sla_mode": "duration", "start_time": start_time, "allowed_seconds": allowed_seconds})
    return result


def _volume_group_column(context: PrimitiveExecutionContext, rows: list[dict[str, Any]], id_column: str) -> str:
    explicit = context.parameters.get("group_key")
    if isinstance(explicit, str) and rows and explicit in rows[0]:
        return explicit
    group_keys = context.parameters.get("group_by_columns") or context.parameters.get("group_keys")
    if isinstance(group_keys, list):
        for item in group_keys:
            if isinstance(item, str) and rows and item in rows[0]:
                return item
    if rows:
        for column in rows[0]:
            if column.endswith("_id") and column != id_column:
                return column
    return id_column


def volume_spike(context: PrimitiveExecutionContext) -> PrimitiveResult:
    table, rows, id_column = _table_and_rows(context)
    if not rows:
        raise ValueError("volume_spike requires at least one candidate row")
    group_column = _volume_group_column(context, rows, id_column)
    groups = list(dict.fromkeys(row.get(group_column) for row in rows))
    selected_indices = _target_indices([{"group": group} for group in groups], context.seed, _rate(context))
    selected_groups = [groups[index] for index in selected_indices]
    baseline_rows = context.dataset.setdefault("__df_volume_baseline", [])
    affected_ids: list[Any] = []
    for offset, group in enumerate(selected_groups, 1):
        group_rows = [row for row in rows if row.get(group_column) == group]
        threshold_ratio = Decimal(str(context.parameters.get("threshold_ratio", "1.5")))
        baseline_rows.append({"baseline_id": f"VOL-SPIKE-{context.seed}-{offset:04d}", "table": table, "group_column": group_column, "group_value": group, "expected_count": len(group_rows), "anomaly_type": "spike", "threshold_ratio": str(threshold_ratio)})
        minimum_observed_count = math.ceil(float(Decimal(len(group_rows)) * threshold_ratio))
        clone_count = max(1, minimum_observed_count - len(group_rows))
        clones = [copy.deepcopy(group_rows[index % len(group_rows)]) for index in range(clone_count)]
        for clone_offset, clone in enumerate(clones, 1):
            clone[id_column] = f"DF_SPIKE_{context.seed}_{offset}_{clone_offset}_{clone.get(id_column)}"
        affected_ids.extend(row.get(id_column) for row in clones)
        rows.extend(clones)
    return PrimitiveResult("volume_spike", context.dataset, len(selected_groups), len(selected_groups), [table], affected_ids, {"table": table, "id_column": id_column, "group_key": group_column, "eligible_row_count": len(groups), "affected_rate_default": _rate(context), "seed": context.seed, "severity": context.severity, "baseline_table": "__df_volume_baseline", "count_semantics": "group_level"})


def volume_drop(context: PrimitiveExecutionContext) -> PrimitiveResult:
    table, rows, id_column = _table_and_rows(context)
    if not rows:
        raise ValueError("volume_drop requires at least one candidate row")
    group_column = _volume_group_column(context, rows, id_column)
    groups = list(dict.fromkeys(row.get(group_column) for row in rows))
    selected_indices = _target_indices([{"group": group} for group in groups], context.seed, _rate(context))
    selected_groups = [groups[index] for index in selected_indices]
    baseline_rows = context.dataset.setdefault("__df_volume_baseline", [])
    affected_ids: list[Any] = []
    for offset, group in enumerate(selected_groups, 1):
        group_indices = [idx for idx, row in enumerate(rows) if row.get(group_column) == group]
        baseline_rows.append({"baseline_id": f"VOL-DROP-{context.seed}-{offset:04d}", "table": table, "group_column": group_column, "group_value": group, "expected_count": len(group_indices), "anomaly_type": "drop", "threshold_ratio": "0.5"})
        remove_count = max(1, len(group_indices))
        for idx in sorted(group_indices[:remove_count], reverse=True):
            affected_ids.append(rows[idx].get(id_column))
            rows.pop(idx)
    return PrimitiveResult("volume_drop", context.dataset, len(selected_groups), len(selected_groups), [table], affected_ids, {"table": table, "id_column": id_column, "group_key": group_column, "eligible_row_count": len(groups), "affected_rate_default": _rate(context), "seed": context.seed, "severity": context.severity, "baseline_table": "__df_volume_baseline", "count_semantics": "group_level"})


def value_below_threshold(context: PrimitiveExecutionContext) -> PrimitiveResult:
    table, rows, id_column = _table_and_rows(context)
    column = _column(context, rows, context.spec.numeric_columns.get(table))
    indices = _target_indices(rows, context.seed, _rate(context))
    threshold = Decimal(str(context.parameters.get("threshold", "0")))
    for index in indices:
        rows[index][column] = str(threshold - Decimal("999"))
    result = _result(context, "value_below_threshold", table, rows, id_column, indices, column)
    result.mutation_metadata.update({"threshold": str(threshold), "operator": "lt"})
    return result


def retry_burst(context: PrimitiveExecutionContext) -> PrimitiveResult:
    table, rows, id_column = _table_and_rows(context)
    if not rows:
        raise ValueError("retry_burst requires at least one candidate row")
    indices = _target_indices(rows, context.seed, _rate(context))
    retry_count = int(context.parameters.get("retry_count", 3))
    baseline_rows = context.dataset.setdefault("__df_retry_baseline", [])
    created_ids: list[Any] = []
    for offset, index in enumerate(indices, 1):
        source = rows[index]
        entity_id = source.get(id_column)
        baseline_rows.append({"baseline_id": f"RTY-{context.seed}-{offset:04d}", "table": table, "id_column": id_column, "entity_id": entity_id, "allowed_attempts": 1})
        for attempt in range(1, retry_count + 1):
            clone = copy.deepcopy(source)
            clone[id_column] = f"DF_RETRY_{context.seed}_{offset}_{attempt}_{entity_id}"
            created_ids.append(clone[id_column])
            rows.append(clone)
    return PrimitiveResult("retry_burst", context.dataset, len(indices), len(indices), [table], [rows[index].get(id_column) for index in indices], {"table": table, "id_column": id_column, "rows_created": len(created_ids), "retry_count": retry_count, "affected_rate_default": _rate(context), "seed": context.seed, "severity": context.severity, "baseline_table": "__df_retry_baseline", "count_semantics": "entity_level"})


def policy_violation(context: PrimitiveExecutionContext) -> PrimitiveResult:
    table, rows, id_column = _table_and_rows(context)
    if not rows:
        raise ValueError("policy_violation requires at least one candidate row")
    column = _column(context, rows, context.spec.numeric_columns.get(table))
    indices = _target_indices(rows, context.seed, _rate(context))
    baseline_rows = context.dataset.setdefault("__df_policy_baseline", [])
    for offset, index in enumerate(indices, 1):
        row = rows[index]
        baseline_rows.append({"baseline_id": f"POL-{context.seed}-{offset:04d}", "policy_id": context.parameters.get("policy_id", "generic_upper_bound"), "policy_type": "upper_bound", "table": table, "id_column": id_column, "entity_id": row.get(id_column), "pk_column": context.spec.schemas[table].primary_key if table in context.spec.schemas else id_column, "pk_value": row.get(context.spec.schemas[table].primary_key) if table in context.spec.schemas else row.get(id_column), "field": column, "limit": "1000", "operator": "lte"})
        row[column] = "5000"
    result = _result(context, "policy_violation", table, rows, id_column, indices, column)
    result.mutation_metadata.update({"baseline_table": "__df_policy_baseline", "policy_type": "upper_bound"})
    return result


def availability_failure(context: PrimitiveExecutionContext) -> PrimitiveResult:
    table, rows, id_column = _table_and_rows(context)
    if not rows:
        raise ValueError("availability_failure requires at least one candidate row")
    column = _status_column(context, rows)
    indices = _target_indices(rows, context.seed, _rate(context))
    baseline_rows = context.dataset.setdefault("__df_availability_baseline", [])
    for offset, index in enumerate(indices, 1):
        row = rows[index]
        baseline_rows.append({"baseline_id": f"AVL-{context.seed}-{offset:04d}", "table": table, "id_column": id_column, "entity_id": row.get(id_column), "pk_column": context.spec.schemas[table].primary_key if table in context.spec.schemas else id_column, "pk_value": row.get(context.spec.schemas[table].primary_key) if table in context.spec.schemas else row.get(id_column), "status_column": column, "available_values": [row.get(column)], "unavailable_value": "DF_UNAVAILABLE"})
        row[column] = "DF_UNAVAILABLE"
    result = _result(context, "availability_failure", table, rows, id_column, indices, column)
    result.mutation_metadata.update({"baseline_table": "__df_availability_baseline", "availability_mode": "status"})
    return result


def geographic_jump(context: PrimitiveExecutionContext) -> PrimitiveResult:
    table, rows, id_column = _table_and_rows(context)
    if not rows:
        raise ValueError("geographic_jump requires at least one candidate row")
    column = str(context.parameters.get("location_column") or "")
    if not column or column not in rows[0]:
        for candidate in ("city", "state", "country", "region", "zone", "latitude", "longitude"):
            if candidate in rows[0]:
                column = candidate
                break
    if not column:
        column = _column(context, rows)
    indices = _target_indices(rows, context.seed, _rate(context))
    baseline_rows = context.dataset.setdefault("__df_geographic_baseline", [])
    for offset, index in enumerate(indices, 1):
        row = rows[index]
        baseline_rows.append({"baseline_id": f"GEO-{context.seed}-{offset:04d}", "table": table, "id_column": id_column, "entity_id": row.get(id_column), "pk_column": context.spec.schemas[table].primary_key if table in context.spec.schemas else id_column, "pk_value": row.get(context.spec.schemas[table].primary_key) if table in context.spec.schemas else row.get(id_column), "location_column": column, "previous_location": row.get(column), "max_distance_km": 1000})
        row[column] = f"DF_IMPOSSIBLE_LOCATION_{context.seed}_{offset}"
    result = _result(context, "geographic_jump", table, rows, id_column, indices, column)
    result.mutation_metadata.update({"baseline_table": "__df_geographic_baseline", "geo_mode": "zone_transition"})
    return result


def build_default_primitive_registry() -> PrimitiveRegistry:
    registry = PrimitiveRegistry()
    registry.register(PrimitiveDefinition("duplicate_entity", "Duplicate selected entities.", "runtime_implemented", duplicate_entity, aliases=("duplicate_transaction",)))
    registry.register(PrimitiveDefinition("null_required_attribute", "Null required attributes.", "runtime_implemented", null_required_attribute, aliases=("set_required_value_null",)))
    registry.register(PrimitiveDefinition("invalid_reference", "Break references.", "runtime_implemented", invalid_reference, aliases=("break_foreign_key", "orphan_child_record")))
    registry.register(PrimitiveDefinition("invalid_datatype", "Inject datatype mismatches.", "runtime_implemented", invalid_datatype, aliases=("datatype_mismatch",)))
    registry.register(PrimitiveDefinition("negative_numeric_value", "Inject negative numeric values.", "runtime_implemented", negative_numeric_value))
    registry.register(PrimitiveDefinition("value_above_threshold", "Inject high outlier values.", "runtime_implemented", value_above_threshold, aliases=("out_of_range_numeric_value", "temperature_threshold_breach", "defect_rate_spike", "dropped_call_rate_spike")))
    registry.register(PrimitiveDefinition("future_timestamp", "Inject invalid/future timestamps.", "runtime_implemented", future_timestamp, aliases=("future_or_invalid_date",)))
    registry.register(PrimitiveDefinition("missing_entity", "Remove selected entities.", "runtime_implemented", missing_entity, aliases=("remove_entity", "missing_child_record")))
    registry.register(PrimitiveDefinition("timestamp_delay", "Delay timestamps beyond expected windows.", "runtime_implemented", timestamp_delay, aliases=("settlement_delay",)))
    registry.register(PrimitiveDefinition("timestamp_out_of_order", "Move selected timestamps before the valid processing sequence.", "runtime_implemented", timestamp_out_of_order))
    registry.register(PrimitiveDefinition("sequence_gap", "Inject deterministic sequence gaps in selected rows/events.", "runtime_implemented", sequence_gap))
    registry.register(PrimitiveDefinition("duplicate_event", "Duplicate selected event/entity rows for sequence validation.", "runtime_implemented", duplicate_event))
    registry.register(PrimitiveDefinition("calculation_error", "Perturb calculated values.", "runtime_implemented", calculation_error, aliases=("grade_formula_error",)))
    registry.register(PrimitiveDefinition("capacity_exceeded", "Exceed capacity/available thresholds.", "runtime_implemented", capacity_exceeded, aliases=("inventory_oversell",)))
    registry.register(PrimitiveDefinition("cross_table_mismatch", "Create an entity-level mismatch against a related/baseline table.", "runtime_implemented", cross_table_mismatch))
    registry.register(PrimitiveDefinition("aggregate_mismatch", "Create a group-level aggregate mismatch.", "runtime_implemented", aggregate_mismatch))
    registry.register(PrimitiveDefinition("invalid_state_transition", "Inject invalid state/status transitions.", "runtime_implemented", invalid_state_transition))
    registry.register(PrimitiveDefinition("stale_timestamp", "Inject stale timestamps beyond configured age SLA.", "runtime_implemented", stale_timestamp))
    registry.register(PrimitiveDefinition("timeout_violation", "Inject elapsed-duration SLA violations.", "runtime_implemented", timeout_violation))
    registry.register(PrimitiveDefinition("volume_spike", "Inject group/window volume spikes.", "runtime_implemented", volume_spike))
    registry.register(PrimitiveDefinition("volume_drop", "Inject group/window volume drops.", "runtime_implemented", volume_drop))
    registry.register(PrimitiveDefinition("value_below_threshold", "Inject values below a configured lower threshold.", "runtime_implemented", value_below_threshold))
    registry.register(PrimitiveDefinition("retry_burst", "Create repeated attempts for selected logical entities.", "runtime_implemented", retry_burst, aliases=("duplicate_retry",)))
    registry.register(PrimitiveDefinition("policy_violation", "Inject structured policy violations.", "runtime_implemented", policy_violation, aliases=("coverage_limit_violation",)))
    registry.register(PrimitiveDefinition("availability_failure", "Inject status-based availability failures.", "runtime_implemented", availability_failure))
    registry.register(PrimitiveDefinition("geographic_jump", "Inject impossible location/zone jumps.", "runtime_implemented", geographic_jump))
    for primitive_id in (
        "duplicate_child_record",
        "orphan_relationship",
        "invalid_enum_value",
        "identity_mismatch",
        "format_corruption",
        "distribution_shift",
        "schema_change",
        "rare_high_value_activity",
    ):
        registry.register(PrimitiveDefinition(primitive_id, f"{primitive_id} is specified but not generically executable yet.", "metadata_only"))
    return registry


PRIMITIVE_REGISTRY = build_default_primitive_registry()
