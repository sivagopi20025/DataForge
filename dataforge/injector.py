from __future__ import annotations

import copy
import random
from typing import Any

from .domains.retail.schemas import RETAIL_SPEC
from .model import AUDIT_COLUMNS, SCD2_COLUMNS, SCENARIO_SUPPORT_COLUMNS, TIME_HIERARCHY_COLUMNS, Dataset, DomainSpec, FailureEvent


DATE_COLUMNS = RETAIL_SPEC.date_columns
NUMERIC_COLUMNS = RETAIL_SPEC.numeric_columns
TYPE_MISMATCH_COLUMNS = RETAIL_SPEC.type_mismatch_columns


class FailureInjector:
    """Shared, deterministic issue injection engine for every domain."""

    def __init__(self, rates: dict[str, float], seed: int = 42, spec: DomainSpec = RETAIL_SPEC) -> None:
        self.rates = rates
        self.rng = random.Random(seed + 1)
        self.spec = spec
        self.seed = seed

    def _indices(self, rows: list[dict[str, Any]], rate: float) -> list[int]:
        if not rows or rate <= 0:
            return []
        count = max(1, int(len(rows) * rate))
        return self.rng.sample(range(len(rows)), min(count, len(rows)))

    def _mutate(
        self,
        data: Dataset,
        table: str,
        failure_type: str,
        column: str,
        value: Any,
    ) -> FailureEvent | None:
        if not data.get(table) or column not in data[table][0]:
            return None
        rate = self.rates.get(failure_type, self.rates.get(failure_type.replace("_records", "s"), 0))
        indices = self._indices(data[table], rate)
        for index in indices:
            data[table][index][column] = value
        return FailureEvent(
            failure_type,
            table,
            column,
            len(indices),
            {
                "requested_rate": rate,
                "eligible_row_count": len(data[table]),
                "selected_row_count": len(indices),
                "actual_affected_count": len(indices),
                "target_locator": [data[table][index].get(self.spec.schemas[table].primary_key) for index in indices],
                "seed": self.seed,
                "severity": "high" if "foreign_key" in failure_type or "datatype" in failure_type else "medium",
            },
        ) if indices else None

    def _schema_drift(self, data: Dataset, table: str, business_columns: list[str]) -> list[FailureEvent]:
        rate = self.rates.get("schema_drift", 0)
        if not rate or not data.get(table) or not business_columns:
            return []
        rows = data[table]
        events: list[FailureEvent] = []
        added_column = "schema_drift_added_column"
        base_details = {
            "requested_rate": rate,
            "eligible_row_count": len(rows),
            "selected_row_count": len(rows),
            "actual_affected_count": 0,
            "seed": self.seed,
            "severity": "medium",
            "schema_version_behavior": "schema_versions_only",
            "expected_validation": "schema_drift_detected",
        }
        events.append(FailureEvent("schema_drift_COLUMN_ADDED", table, added_column, 0, {**base_details, "drift_type": "column_added"}))

        removed_column = business_columns[-1]
        events.append(FailureEvent("schema_drift_COLUMN_REMOVED", table, removed_column, 0, {**base_details, "drift_type": "column_removed"}))

        rename_source = next((column for column in business_columns if column in rows[0]), None)
        if rename_source:
            renamed = f"{rename_source}_renamed"
            events.append(FailureEvent("schema_drift_COLUMN_RENAMED", table, rename_source, 0, {**base_details, "drift_type": "column_renamed", "renamed_to": renamed}))

        type_column = next((column for column in business_columns if column in rows[0]), None)
        if type_column:
            events.append(FailureEvent("schema_drift_DATATYPE_CHANGED", table, type_column, 0, {**base_details, "drift_type": "datatype_changed", "new_type": "string"}))

        nullable_column = next((column for column in business_columns if column in rows[0]), None)
        if nullable_column:
            events.append(FailureEvent("schema_drift_NULLABILITY_CHANGED", table, nullable_column, 0, {**base_details, "drift_type": "nullability_changed", "nullable": True}))

        events.append(FailureEvent("schema_drift_COLUMN_ORDER_CHANGED", table, None, 0, {**base_details, "drift_type": "column_order_changed"}))
        return events

    def apply(self, source: Dataset, selected_tables: set[str] | None = None) -> tuple[Dataset, list[FailureEvent]]:
        data = copy.deepcopy(source)
        selected = selected_tables or set(data)
        events: list[FailureEvent] = []

        for table in sorted(selected):
            if table not in data:
                continue
            rows = data[table]
            if not rows:
                if self.rates:
                    events.append(FailureEvent("injection_skipped_zero_rows", table, None, 0, {"reason": "records=0; no eligible rows", "seed": self.seed, "severity": "info"}))
                continue
            schema = self.spec.schemas[table]
            business_columns = [column for column in schema.columns if column not in {
                schema.primary_key,
                *AUDIT_COLUMNS,
                *TIME_HIERARCHY_COLUMNS,
                *SCD2_COLUMNS,
                *SCENARIO_SUPPORT_COLUMNS,
            }]
            if not business_columns:
                continue

            fk_columns = {fk.column for fk in schema.foreign_keys}
            drift_columns = [column for column in business_columns if column not in fk_columns]
            events.extend(self._schema_drift(data, table, drift_columns))

            nullable_target = next((column for column in business_columns if rows and column in rows[0]), None)
            event = self._mutate(data, table, "null_values", nullable_target, "") if nullable_target else None
            if not event:
                event = self._mutate(data, table, "nulls", nullable_target, "") if nullable_target else None
            if event:
                events.append(event)

            type_column = self.spec.type_mismatch_columns.get(table)
            if type_column:
                original = next((row[type_column] for row in rows if row.get(type_column) not in ("", None)), "")
                mismatch_value: Any = 999999 if isinstance(original, str) else "ABCXYZ"
                event = self._mutate(data, table, "datatype_mismatch", type_column, mismatch_value)
                if event:
                    events.append(event)

            if schema.foreign_keys:
                fk_column = schema.foreign_keys[0].column
                event = self._mutate(data, table, "foreign_key_break", fk_column, 999999999)
                if not event:
                    event = self._mutate(data, table, "fk_break", fk_column, 999999999)
                if event:
                    events.append(event)

            date_column = self.spec.date_columns.get(table)
            if date_column:
                event = self._mutate(data, table, "invalid_dates", date_column, "2035-15-99")
                if event:
                    events.append(event)

            numeric_column = self.spec.numeric_columns.get(table)
            if numeric_column:
                event = self._mutate(data, table, "negative_values", numeric_column, -500)
                if event:
                    events.append(event)
                event = self._mutate(data, table, "outliers", numeric_column, 99999999)
                if event:
                    events.append(event)

            duplicate_indices = self._indices(rows, self.rates.get("duplicate_records", self.rates.get("duplicates", 0)))
            rows.extend(copy.deepcopy(rows[index]) for index in duplicate_indices)
            if duplicate_indices:
                events.append(FailureEvent("duplicate_records", table, schema.primary_key, len(duplicate_indices), {
                    "requested_rate": self.rates.get("duplicate_records", self.rates.get("duplicates", 0)),
                    "eligible_row_count": len(rows) - len(duplicate_indices),
                    "selected_row_count": len(duplicate_indices),
                    "actual_affected_count": len(duplicate_indices),
                    "target_locator": [rows[index].get(schema.primary_key) for index in duplicate_indices],
                    "seed": self.seed,
                    "severity": "medium",
                    "expected_validation": "duplicate_records",
                }))

            missing_indices = self._indices(rows, self.rates.get("missing_records", 0))
            for index in sorted(missing_indices, reverse=True):
                rows.pop(index)
            if missing_indices:
                events.append(FailureEvent("missing_records", table, schema.primary_key, len(missing_indices), {
                    "requested_rate": self.rates.get("missing_records", 0),
                    "eligible_row_count": len(rows) + len(missing_indices),
                    "selected_row_count": len(missing_indices),
                    "actual_affected_count": len(missing_indices),
                    "seed": self.seed,
                    "severity": "high",
                    "expected_validation": "missing_records",
                }))

        return data, events
