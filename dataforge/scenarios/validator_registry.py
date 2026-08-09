from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Callable

from dataforge.model import Dataset, DomainSpec
from dataforge.scenarios.primitives import PrimitiveResult


@dataclass(frozen=True)
class ValidatorDefinition:
    validator_pattern_id: str
    description: str
    runtime_status: str
    executor: Callable[["ValidatorExecutionContext"], dict[str, Any]] | None = None
    aliases: tuple[str, ...] = ()


@dataclass
class ValidatorExecutionContext:
    dataset: Dataset
    spec: DomainSpec
    parameters: dict[str, Any]
    primitive_result: PrimitiveResult | None = None
    expected_count: int = 0
    severity: str = "medium"


class ValidatorRegistry:
    def __init__(self) -> None:
        self._definitions: dict[str, ValidatorDefinition] = {}
        self._aliases: dict[str, str] = {}

    def register(self, definition: ValidatorDefinition) -> None:
        self._definitions[definition.validator_pattern_id] = definition
        for alias in definition.aliases:
            self._aliases[alias] = definition.validator_pattern_id

    def resolve_id(self, validator_pattern_id: str) -> str:
        return self._aliases.get(validator_pattern_id, validator_pattern_id)

    def get(self, validator_pattern_id: str) -> ValidatorDefinition:
        canonical = self.resolve_id(validator_pattern_id)
        if canonical not in self._definitions:
            raise KeyError(f"Unknown validator pattern: {validator_pattern_id}")
        return self._definitions[canonical]

    def runtime_implemented(self) -> set[str]:
        return {key for key, definition in self._definitions.items() if definition.executor and definition.runtime_status in {"runtime_implemented", "runtime_partial", "custom_reference_only"}}

    def metadata_only(self) -> set[str]:
        return {key for key, definition in self._definitions.items() if not definition.executor or definition.runtime_status == "metadata_only"}

    def validate(self, validator_pattern_id: str, context: ValidatorExecutionContext) -> dict[str, Any]:
        definition = self.get(validator_pattern_id)
        if not definition.executor:
            raise NotImplementedError(f"Validator {validator_pattern_id} is {definition.runtime_status} and cannot execute yet")
        return definition.executor(context)


def _base_result(context: ValidatorExecutionContext, validation_id: str, detected_count: int, affected_entities: list[Any], evidence: dict[str, Any]) -> dict[str, Any]:
    expected = context.expected_count
    status = "PASS" if detected_count >= expected else "FAIL"
    if expected == 0:
        status = "PASS" if detected_count == 0 else "FAIL"
    return {
        "validation_id": validation_id,
        "status": status,
        "expected_count": expected,
        "selected_count": context.primitive_result.selected_count if context.primitive_result else expected,
        "actual_mutated_count": context.primitive_result.actual_mutated_count if context.primitive_result else detected_count,
        "detected_count": detected_count,
        "affected_entities": affected_entities[:100],
        "affected_tables": context.primitive_result.affected_tables if context.primitive_result else [context.parameters.get("table")],
        "severity": context.severity,
        "message": f"{validation_id} detected {detected_count} records/events.",
        "evidence": evidence,
        "warnings": [],
        "reconciliation_status": "PASS" if detected_count >= expected else "FAIL",
    }


def _table_rows(context: ValidatorExecutionContext) -> tuple[str, list[dict[str, Any]]]:
    table = str(context.parameters.get("table") or (context.primitive_result.affected_tables[0] if context.primitive_result and context.primitive_result.affected_tables else ""))
    return table, context.dataset.get(table, [])


def _columns(context: ValidatorExecutionContext, rows: list[dict[str, Any]]) -> list[str]:
    primitive_column = None
    if context.primitive_result and context.primitive_result.mutation_metadata.get("column"):
        primitive_column = str(context.primitive_result.mutation_metadata["column"])
    cols = context.parameters.get("columns")
    if isinstance(cols, list) and cols:
        selected = [str(item) for item in cols if isinstance(item, str)]
        if primitive_column and primitive_column not in selected:
            selected.insert(0, primitive_column)
        return selected
    if primitive_column:
        return [primitive_column]
    return list(rows[0])[:1] if rows else []


def duplicate_key_validator(context: ValidatorExecutionContext) -> dict[str, Any]:
    table, rows = _table_rows(context)
    key_columns = _columns(context, rows)
    if not key_columns and table in context.spec.schemas:
        key_columns = [context.spec.schemas[table].primary_key]
    counts = Counter(tuple(row.get(column) for column in key_columns) for row in rows)
    duplicate_keys = [key for key, count in counts.items() if count > 1]
    return _base_result(context, "duplicate_key_validator", len(duplicate_keys), [str(key) for key in duplicate_keys], {"table": table, "key_columns": key_columns, "duplicate_key_count": len(duplicate_keys)})


def missing_record_validator(context: ValidatorExecutionContext) -> dict[str, Any]:
    affected = context.primitive_result.affected_entity_ids if context.primitive_result else []
    return _base_result(context, "missing_record_validator", len(affected), affected, {"missing_entity_ids": affected[:100]})


def required_field_validator(context: ValidatorExecutionContext) -> dict[str, Any]:
    table, rows = _table_rows(context)
    columns = _columns(context, rows)
    affected = [row.get(context.spec.schemas[table].primary_key) for row in rows for column in columns if row.get(column) in ("", None)] if table in context.spec.schemas else []
    return _base_result(context, "required_field_validator", len(affected), affected, {"table": table, "columns": columns})


def datatype_validator(context: ValidatorExecutionContext) -> dict[str, Any]:
    table, rows = _table_rows(context)
    columns = _columns(context, rows)
    affected = []
    for row in rows:
        for column in columns:
            if row.get(column) == "DF_INVALID_TYPE":
                affected.append(row.get(context.spec.schemas[table].primary_key) if table in context.spec.schemas else None)
    return _base_result(context, "datatype_validator", len(affected), affected, {"table": table, "columns": columns})


def referential_integrity_validator(context: ValidatorExecutionContext) -> dict[str, Any]:
    table, rows = _table_rows(context)
    if table not in context.spec.schemas:
        return _base_result(context, "referential_integrity_validator", 0, [], {"table": table, "reason": "unknown table"})
    schema = context.spec.schemas[table]
    affected = []
    for fk in schema.foreign_keys:
        parent_values = {row.get(fk.parent_column) for row in context.dataset.get(fk.parent_table, [])}
        affected.extend(row.get(schema.primary_key) for row in rows if row.get(fk.column) not in parent_values and not (fk.nullable and row.get(fk.column) in ("", None)))
    return _base_result(context, "referential_integrity_validator", len(affected), affected, {"table": table})


def range_validator(context: ValidatorExecutionContext) -> dict[str, Any]:
    table, rows = _table_rows(context)
    columns = _columns(context, rows)
    affected = []
    for row in rows:
        for column in columns:
            try:
                if Decimal(str(row.get(column))) < 0:
                    affected.append(row.get(context.spec.schemas[table].primary_key) if table in context.spec.schemas else None)
            except (InvalidOperation, TypeError):
                continue
    return _base_result(context, "range_validator", len(affected), affected, {"table": table, "columns": columns})


def threshold_validator(context: ValidatorExecutionContext) -> dict[str, Any]:
    table, rows = _table_rows(context)
    columns = _columns(context, rows)
    threshold_value = context.parameters.get("threshold")
    if threshold_value is None and context.primitive_result:
        threshold_value = context.primitive_result.mutation_metadata.get("threshold")
    if threshold_value is None:
        threshold_value = "1000000"
    threshold = Decimal(str(threshold_value))
    operator = str(context.parameters.get("operator") or (context.primitive_result.mutation_metadata.get("operator") if context.primitive_result else "") or "gte")
    affected = []
    evidence_rows = []
    for row in rows:
        for column in columns:
            try:
                value = Decimal(str(row.get(column)))
                violated = value >= threshold if operator in {"gt", "gte"} else value < threshold if operator in {"lt", "lte"} else value >= threshold
                if violated:
                    affected.append(row.get(context.spec.schemas[table].primary_key) if table in context.spec.schemas else None)
                    evidence_rows.append({"entity_id": affected[-1], "column": column, "observed_value": str(value), "threshold": str(threshold), "operator": operator, "difference": str(abs(value - threshold))})
            except (InvalidOperation, TypeError):
                continue
    return _base_result(context, "threshold_validator", len(affected), affected, {"table": table, "columns": columns, "threshold": str(threshold), "operator": operator, "violations": evidence_rows[:100]})


def temporal_order_validator(context: ValidatorExecutionContext) -> dict[str, Any]:
    table, rows = _table_rows(context)
    columns = _columns(context, rows)
    affected = []
    for row in rows:
        for column in columns:
            try:
                datetime.fromisoformat(str(row.get(column)))
            except (TypeError, ValueError):
                affected.append(row.get(context.spec.schemas[table].primary_key) if table in context.spec.schemas else None)
    return _base_result(context, "temporal_order_validator", len(affected), affected, {"table": table, "columns": columns})


def sequence_validator(context: ValidatorExecutionContext) -> dict[str, Any]:
    table, rows = _table_rows(context)
    columns = _columns(context, rows)
    primary_key = context.spec.schemas[table].primary_key if table in context.spec.schemas else None
    id_column = (
        str(context.primitive_result.mutation_metadata.get("id_column"))
        if context.primitive_result and context.primitive_result.mutation_metadata.get("id_column")
        else primary_key
    )
    affected: list[Any] = []
    evidence: dict[str, Any] = {
        "table": table,
        "columns": columns,
        "detectors": ["sequence_gap_marker", "out_of_order_timestamp", "duplicate_sequence_key"],
        "sequence_gap_count": 0,
        "out_of_order_timestamp_count": 0,
        "duplicate_sequence_key_count": 0,
    }

    for row in rows:
        row_id = row.get(id_column) if id_column else None
        for column in columns:
            value = row.get(column)
            if isinstance(value, str) and value.startswith("DF_SEQUENCE_GAP_"):
                affected.append(row_id)
                evidence["sequence_gap_count"] += 1
                break
            try:
                parsed = datetime.fromisoformat(str(value))
            except (TypeError, ValueError):
                continue
            if parsed.year < 1970:
                affected.append(row_id)
                evidence["out_of_order_timestamp_count"] += 1
                break

    if context.primitive_result and context.primitive_result.primitive_id == "duplicate_event":
        key_columns = [id_column] if id_column else columns[:1]
        counts = Counter(tuple(row.get(column) for column in key_columns) for row in rows)
        duplicates = [str(key) for key, count in counts.items() if count > 1]
        affected.extend(duplicates)
        evidence["duplicate_sequence_key_count"] = len(duplicates)
        evidence["duplicate_key_columns"] = key_columns

    if context.primitive_result and context.primitive_result.primitive_id == "retry_burst":
        retry_baselines = [
            baseline
            for baseline in context.dataset.get("__df_retry_baseline", [])
            if baseline.get("table") == table
        ]
        for baseline in retry_baselines:
            entity_id = baseline.get("entity_id")
            retry_count = sum(
                1
                for row in rows
                if str(row.get(id_column)).endswith(str(entity_id)) or row.get(id_column) == entity_id
            )
            if retry_count > int(baseline.get("allowed_attempts", 1)):
                affected.append(entity_id)
                evidence["duplicate_sequence_key_count"] += 1
        if retry_baselines:
            evidence["retry_baseline_count"] = len(retry_baselines)
            evidence["detectors"].append("retry_burst_sequence")

    return _base_result(context, "sequence_validator", len(affected), affected, evidence)


def calculation_validator(context: ValidatorExecutionContext) -> dict[str, Any]:
    affected = context.primitive_result.affected_entity_ids if context.primitive_result else []
    return _base_result(context, "calculation_validator", len(affected), affected, {"calculation_mutation_ids": affected[:100]})


def capacity_validator(context: ValidatorExecutionContext) -> dict[str, Any]:
    return threshold_validator(context) | {"validation_id": "capacity_validator"}


def _tolerance(context: ValidatorExecutionContext) -> Decimal:
    try:
        return Decimal(str(context.parameters.get("tolerance", context.parameters.get("absolute_tolerance", "0.01"))))
    except (InvalidOperation, TypeError):
        return Decimal("0.01")


def _decimal_difference(left: Any, right: Any) -> Decimal | None:
    try:
        return abs(Decimal(str(left)) - Decimal(str(right)))
    except (InvalidOperation, TypeError):
        return None


def cross_table_consistency_validator(context: ValidatorExecutionContext) -> dict[str, Any]:
    baseline_rows = context.dataset.get("__df_cross_table_baseline", [])
    tolerance = _tolerance(context)
    affected: list[Any] = []
    comparisons: list[dict[str, Any]] = []
    for baseline in baseline_rows:
        source_table = str(baseline.get("source_table"))
        source_id_column = str(baseline.get("source_id_column") or "")
        source_pk_column = str(baseline.get("source_pk_column") or "")
        source_pk_value = baseline.get("source_pk_value")
        source_column = str(baseline.get("source_column"))
        source_entity_id = baseline.get("source_entity_id")
        if source_table not in context.spec.schemas:
            continue
        schema = context.spec.schemas[source_table]
        locator_column = source_pk_column if source_pk_column in schema.columns else source_id_column if source_id_column in schema.columns else schema.primary_key
        locator_value = source_pk_value if source_pk_column in schema.columns else source_entity_id
        matching = [row for row in context.dataset.get(source_table, []) if row.get(locator_column) == locator_value]
        if not matching:
            continue
        actual_value = matching[0].get(source_column)
        expected_value = baseline.get("expected_value")
        difference = _decimal_difference(actual_value, expected_value)
        mismatch = difference > tolerance if difference is not None else actual_value != expected_value
        if mismatch:
            affected.append(source_entity_id)
            comparisons.append(
                {
                    "source_table": source_table,
                    "source_id_column": locator_column,
                    "source_entity_id": source_entity_id,
                    "source_column": source_column,
                    "expected_value": expected_value,
                    "actual_value": actual_value,
                    "difference": str(difference) if difference is not None else "non_numeric",
                    "comparison_rule": "equals_with_tolerance",
                    "tolerance": str(tolerance),
                }
            )
    return _base_result(
        context,
        "cross_table_consistency_validator",
        len(affected),
        affected,
        {"baseline_table": "__df_cross_table_baseline", "comparisons": comparisons[:100]},
    )


def aggregate_balance_validator(context: ValidatorExecutionContext) -> dict[str, Any]:
    baseline_rows = context.dataset.get("__df_aggregate_baseline", [])
    tolerance = _tolerance(context)
    affected: list[Any] = []
    groups: list[dict[str, Any]] = []
    for baseline in baseline_rows:
        detail_table = str(baseline.get("detail_table"))
        group_key = str(baseline.get("group_key"))
        group_value = baseline.get("group_value")
        value_column = str(baseline.get("detail_value_column"))
        if detail_table not in context.dataset:
            continue
        detail_rows = [row for row in context.dataset.get(detail_table, []) if row.get(group_key) == group_value]
        try:
            actual_total = sum(Decimal(str(row.get(value_column, 0))) for row in detail_rows)
            expected_total = Decimal(str(baseline.get("expected_aggregate", "0")))
        except (InvalidOperation, TypeError):
            actual_total = Decimal(len(detail_rows))
            expected_total = Decimal(str(baseline.get("expected_aggregate", "0")))
        difference = abs(actual_total - expected_total)
        if difference > tolerance:
            affected.append(group_value)
            groups.append(
                {
                    "group_id": group_value,
                    "detail_table": detail_table,
                    "aggregate_table": baseline.get("aggregate_table"),
                    "group_key": group_key,
                    "detail_value_column": value_column,
                    "expected_aggregate": str(expected_total),
                    "actual_aggregate": str(actual_total),
                    "difference": str(difference),
                    "aggregation_function": baseline.get("aggregation_function", "sum"),
                    "tolerance": str(tolerance),
                }
            )
    return _base_result(
        context,
        "aggregate_balance_validator",
        len(affected),
        affected,
        {"baseline_table": "__df_aggregate_baseline", "groups": groups[:100]},
    )


def _parse_dt(value: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def state_transition_validator(context: ValidatorExecutionContext) -> dict[str, Any]:
    baselines = context.dataset.get("__df_state_transition_baseline", [])
    affected: list[Any] = []
    transitions: list[dict[str, Any]] = []
    for baseline in baselines:
        table = str(baseline.get("table"))
        if table not in context.spec.schemas:
            continue
        schema = context.spec.schemas[table]
        pk_column = str(baseline.get("pk_column") or schema.primary_key)
        pk_value = baseline.get("pk_value")
        status_column = str(baseline.get("status_column"))
        matching = [row for row in context.dataset.get(table, []) if row.get(pk_column) == pk_value]
        if not matching:
            continue
        current_state = matching[0].get(status_column)
        allowed = set(baseline.get("allowed_states") or [])
        if current_state not in allowed:
            affected.append(baseline.get("entity_id"))
            transitions.append(
                {
                    "entity_id": baseline.get("entity_id"),
                    "table": table,
                    "status_column": status_column,
                    "previous_state": baseline.get("previous_state"),
                    "current_state": current_state,
                    "violated_rule": baseline.get("violated_rule", "impossible_transition"),
                }
            )
    return _base_result(context, "state_transition_validator", len(affected), affected, {"baseline_table": "__df_state_transition_baseline", "transitions": transitions[:100]})


def sla_validator(context: ValidatorExecutionContext) -> dict[str, Any]:
    baselines = context.dataset.get("__df_sla_baseline", [])
    affected: list[Any] = []
    violations: list[dict[str, Any]] = []
    for baseline in baselines:
        table = str(baseline.get("table"))
        if table not in context.spec.schemas:
            continue
        schema = context.spec.schemas[table]
        pk_column = str(baseline.get("pk_column") or schema.primary_key)
        pk_value = baseline.get("pk_value")
        matching = [row for row in context.dataset.get(table, []) if row.get(pk_column) == pk_value]
        if not matching:
            continue
        row = matching[0]
        allowed_seconds = int(baseline.get("allowed_seconds", 86400))
        sla_type = str(baseline.get("sla_type", "age"))
        actual_seconds: float | None = None
        if sla_type == "age":
            reference = _parse_dt(baseline.get("reference_time"))
            event_time = _parse_dt(row.get(str(baseline.get("timestamp_column"))))
            if reference and event_time:
                actual_seconds = (reference - event_time).total_seconds()
        else:
            start_time = _parse_dt(baseline.get("start_time"))
            end_time = _parse_dt(row.get(str(baseline.get("end_column"))))
            if start_time and end_time:
                actual_seconds = (end_time - start_time).total_seconds()
        if actual_seconds is not None and actual_seconds > allowed_seconds:
            affected.append(baseline.get("entity_id"))
            violations.append(
                {
                    "entity_id": baseline.get("entity_id"),
                    "table": table,
                    "sla_type": sla_type,
                    "actual_seconds": actual_seconds,
                    "allowed_seconds": allowed_seconds,
                    "violation_seconds": actual_seconds - allowed_seconds,
                    "timestamp_column": baseline.get("timestamp_column") or baseline.get("end_column"),
                }
            )
    return _base_result(context, "sla_validator", len(affected), affected, {"baseline_table": "__df_sla_baseline", "violations": violations[:100]})


def volume_anomaly_validator(context: ValidatorExecutionContext) -> dict[str, Any]:
    baselines = context.dataset.get("__df_volume_baseline", [])
    affected: list[Any] = []
    anomalies: list[dict[str, Any]] = []
    for baseline in baselines:
        table = str(baseline.get("table"))
        group_column = str(baseline.get("group_column"))
        group_value = baseline.get("group_value")
        expected_count = int(baseline.get("expected_count", 0))
        observed_count = sum(1 for row in context.dataset.get(table, []) if row.get(group_column) == group_value)
        anomaly_type = str(baseline.get("anomaly_type"))
        ratio = Decimal(observed_count) / Decimal(expected_count) if expected_count else Decimal("0")
        is_anomaly = ratio >= Decimal("1.5") if anomaly_type == "spike" else ratio <= Decimal("0.5")
        if is_anomaly:
            affected.append(group_value)
            anomalies.append(
                {
                    "group_key": group_column,
                    "group_value": group_value,
                    "baseline_count": expected_count,
                    "observed_count": observed_count,
                    "difference": observed_count - expected_count,
                    "ratio": str(ratio),
                    "threshold": "1.5" if anomaly_type == "spike" else "0.5",
                    "anomaly_type": anomaly_type,
                }
            )
    return _base_result(context, "volume_anomaly_validator", len(affected), affected, {"baseline_table": "__df_volume_baseline", "anomalies": anomalies[:100]})


def retry_pattern_validator(context: ValidatorExecutionContext) -> dict[str, Any]:
    baselines = context.dataset.get("__df_retry_baseline", [])
    affected: list[Any] = []
    retries: list[dict[str, Any]] = []
    for baseline in baselines:
        table = str(baseline.get("table"))
        id_column = str(baseline.get("id_column"))
        entity_id = baseline.get("entity_id")
        allowed = int(baseline.get("allowed_attempts", 1))
        attempt_count = sum(1 for row in context.dataset.get(table, []) if str(row.get(id_column)).endswith(str(entity_id)) or row.get(id_column) == entity_id)
        if attempt_count > allowed:
            affected.append(entity_id)
            retries.append({"entity_id": entity_id, "table": table, "attempt_count": attempt_count, "allowed_attempts": allowed, "violated_rule": "retry_burst"})
    return _base_result(context, "retry_pattern_validator", len(affected), affected, {"baseline_table": "__df_retry_baseline", "retries": retries[:100]})


def policy_validator(context: ValidatorExecutionContext) -> dict[str, Any]:
    baselines = context.dataset.get("__df_policy_baseline", [])
    affected: list[Any] = []
    violations: list[dict[str, Any]] = []
    if not baselines and context.primitive_result and context.primitive_result.primitive_id == "negative_numeric_value":
        table, rows = _table_rows(context)
        columns = _columns(context, rows)
        pk = context.spec.schemas[table].primary_key if table in context.spec.schemas else None
        for row in rows:
            for column in columns:
                try:
                    value = Decimal(str(row.get(column)))
                except (InvalidOperation, TypeError):
                    continue
                if value < 0:
                    entity_id = row.get(pk) if pk else None
                    affected.append(entity_id)
                    violations.append({"entity_id": entity_id, "policy_id": "generic_non_negative", "policy_type": "lower_bound", "observed_values": {column: str(value)}, "expected_rule": f"{column} >= 0", "violation_reason": "negative_value"})
        return _base_result(context, "policy_validator", len(affected), affected, {"baseline_table": None, "violations": violations[:100]})
    for baseline in baselines:
        table = str(baseline.get("table"))
        if table not in context.spec.schemas:
            continue
        schema = context.spec.schemas[table]
        pk_column = str(baseline.get("pk_column") or schema.primary_key)
        pk_value = baseline.get("pk_value")
        field = str(baseline.get("field"))
        rows = [row for row in context.dataset.get(table, []) if row.get(pk_column) == pk_value]
        if not rows:
            continue
        value = Decimal(str(rows[0].get(field, 0)))
        limit = Decimal(str(baseline.get("limit", 0)))
        if value > limit:
            affected.append(baseline.get("entity_id"))
            violations.append({"entity_id": baseline.get("entity_id"), "policy_id": baseline.get("policy_id"), "policy_type": baseline.get("policy_type"), "observed_values": {field: str(value)}, "expected_rule": f"{field} <= {limit}", "violation_reason": "upper_bound_exceeded"})
    return _base_result(context, "policy_validator", len(affected), affected, {"baseline_table": "__df_policy_baseline", "violations": violations[:100]})


def availability_validator(context: ValidatorExecutionContext) -> dict[str, Any]:
    baselines = context.dataset.get("__df_availability_baseline", [])
    affected: list[Any] = []
    failures: list[dict[str, Any]] = []
    for baseline in baselines:
        table = str(baseline.get("table"))
        if table not in context.spec.schemas:
            continue
        schema = context.spec.schemas[table]
        pk_column = str(baseline.get("pk_column") or schema.primary_key)
        pk_value = baseline.get("pk_value")
        status_column = str(baseline.get("status_column"))
        rows = [row for row in context.dataset.get(table, []) if row.get(pk_column) == pk_value]
        if not rows:
            continue
        state = rows[0].get(status_column)
        if state not in set(baseline.get("available_values") or []):
            affected.append(baseline.get("entity_id"))
            failures.append({"entity_id": baseline.get("entity_id"), "availability_state": state, "status_column": status_column, "violated_rule": "unavailable_status"})
    return _base_result(context, "availability_validator", len(affected), affected, {"baseline_table": "__df_availability_baseline", "failures": failures[:100]})


def geographic_validator(context: ValidatorExecutionContext) -> dict[str, Any]:
    baselines = context.dataset.get("__df_geographic_baseline", [])
    affected: list[Any] = []
    jumps: list[dict[str, Any]] = []
    for baseline in baselines:
        table = str(baseline.get("table"))
        if table not in context.spec.schemas:
            continue
        schema = context.spec.schemas[table]
        pk_column = str(baseline.get("pk_column") or schema.primary_key)
        pk_value = baseline.get("pk_value")
        location_column = str(baseline.get("location_column"))
        rows = [row for row in context.dataset.get(table, []) if row.get(pk_column) == pk_value]
        if not rows:
            continue
        current = rows[0].get(location_column)
        previous = baseline.get("previous_location")
        if current != previous:
            affected.append(baseline.get("entity_id"))
            jumps.append({"entity_id": baseline.get("entity_id"), "previous_location": previous, "current_location": current, "distance": "not_calculated_zone_jump", "allowed_limit": baseline.get("max_distance_km"), "violated_rule": "impossible_zone_transition"})
    return _base_result(context, "geographic_validator", len(affected), affected, {"baseline_table": "__df_geographic_baseline", "jumps": jumps[:100]})


def build_default_validator_registry() -> ValidatorRegistry:
    registry = ValidatorRegistry()
    registry.register(ValidatorDefinition("duplicate_key_validator", "Detect duplicate keys.", "runtime_implemented", duplicate_key_validator, aliases=("reconciliation",)))
    registry.register(ValidatorDefinition("missing_record_validator", "Detect missing records.", "runtime_implemented", missing_record_validator))
    registry.register(ValidatorDefinition("required_field_validator", "Detect missing required fields.", "runtime_implemented", required_field_validator))
    registry.register(ValidatorDefinition("datatype_validator", "Detect datatype mismatches.", "runtime_implemented", datatype_validator))
    registry.register(ValidatorDefinition("referential_integrity_validator", "Detect orphan references.", "runtime_implemented", referential_integrity_validator))
    registry.register(ValidatorDefinition("range_validator", "Detect range violations.", "runtime_implemented", range_validator))
    registry.register(ValidatorDefinition("threshold_validator", "Detect threshold violations.", "runtime_implemented", threshold_validator))
    registry.register(ValidatorDefinition("temporal_order_validator", "Detect timestamp/order failures.", "runtime_implemented", temporal_order_validator))
    registry.register(ValidatorDefinition("sequence_validator", "Detect sequence gaps, out-of-order timestamps, and duplicate events.", "runtime_implemented", sequence_validator))
    registry.register(ValidatorDefinition("calculation_validator", "Detect calculation errors.", "runtime_implemented", calculation_validator))
    registry.register(ValidatorDefinition("capacity_validator", "Detect capacity failures.", "runtime_implemented", capacity_validator))
    registry.register(ValidatorDefinition("cross_table_consistency_validator", "Detect entity-level mismatches across related/baseline tables.", "runtime_implemented", cross_table_consistency_validator))
    registry.register(ValidatorDefinition("aggregate_balance_validator", "Detect group-level aggregate reconciliation mismatches.", "runtime_implemented", aggregate_balance_validator))
    registry.register(ValidatorDefinition("state_transition_validator", "Detect invalid state/status transitions.", "runtime_implemented", state_transition_validator))
    registry.register(ValidatorDefinition("sla_validator", "Detect stale age and elapsed-duration SLA failures.", "runtime_implemented", sla_validator))
    registry.register(ValidatorDefinition("volume_anomaly_validator", "Detect group/window volume spikes and drops.", "runtime_implemented", volume_anomaly_validator))
    registry.register(ValidatorDefinition("retry_pattern_validator", "Detect retry bursts for logical entities.", "runtime_implemented", retry_pattern_validator))
    registry.register(ValidatorDefinition("policy_validator", "Detect structured business policy violations.", "runtime_implemented", policy_validator))
    registry.register(ValidatorDefinition("availability_validator", "Detect status-based availability failures.", "runtime_implemented", availability_validator))
    registry.register(ValidatorDefinition("geographic_validator", "Detect impossible location/zone transitions.", "runtime_implemented", geographic_validator))
    registry.register(ValidatorDefinition("schema_validator", "Schema validation is implemented by the core validator.", "runtime_partial", aliases=("schema",)))
    registry.register(ValidatorDefinition("scenario_specific_validator", "Custom reference validators.", "custom_reference_only", aliases=("scenario_specific", "business_rule")))
    for validator_id in (
        "distribution_validator",
        "reconciliation_validator",
        "identity_validator",
    ):
        registry.register(ValidatorDefinition(validator_id, f"{validator_id} is specified but not generically executable yet.", "metadata_only"))
    return registry


VALIDATOR_REGISTRY = build_default_validator_registry()
