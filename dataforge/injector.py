from __future__ import annotations

import copy
import random
from typing import Any

from .domains.retail.schemas import RETAIL_SPEC
from .model import AUDIT_COLUMNS, SCD2_COLUMNS, TIME_HIERARCHY_COLUMNS, Dataset, DomainSpec, FailureEvent


DATE_COLUMNS = RETAIL_SPEC.date_columns
NUMERIC_COLUMNS = RETAIL_SPEC.numeric_columns
TYPE_MISMATCH_COLUMNS = RETAIL_SPEC.type_mismatch_columns


class FailureInjector:
    """Shared, deterministic issue injection engine for every domain."""

    def __init__(self, rates: dict[str, float], seed: int = 42, spec: DomainSpec = RETAIL_SPEC) -> None:
        self.rates = rates
        self.rng = random.Random(seed + 1)
        self.spec = spec

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
        indices = self._indices(data[table], self.rates.get(failure_type, self.rates.get(failure_type.replace("_records", "s"), 0)))
        for index in indices:
            data[table][index][column] = value
        return FailureEvent(failure_type, table, column, len(indices)) if indices else None

    def _schema_drift(self, data: Dataset, table: str, business_columns: list[str]) -> list[FailureEvent]:
        rate = self.rates.get("schema_drift", 0)
        if not rate or not data.get(table) or not business_columns:
            return []
        rows = data[table]
        events: list[FailureEvent] = []
        added_column = "schema_drift_added_column"
        for row in rows:
            row[added_column] = "drift"
        events.append(FailureEvent("schema_drift_COLUMN_ADDED", table, added_column, len(rows)))

        removed_column = business_columns[-1]
        for row in rows:
            row.pop(removed_column, None)
        events.append(FailureEvent("schema_drift_COLUMN_REMOVED", table, removed_column, len(rows)))

        rename_source = next((column for column in business_columns if column in rows[0]), None)
        if rename_source:
            renamed = f"{rename_source}_renamed"
            for row in rows:
                row[renamed] = row.pop(rename_source, "")
            events.append(FailureEvent("schema_drift_COLUMN_RENAMED", table, rename_source, len(rows), {"renamed_to": renamed}))

        type_column = next((column for column in business_columns if column in rows[0]), None)
        if type_column:
            for row in rows[: max(1, len(rows) // 10)]:
                row[type_column] = {"unexpected": "object"}
            events.append(FailureEvent("schema_drift_DATATYPE_CHANGED", table, type_column, max(1, len(rows) // 10)))

        nullable_column = next((column for column in business_columns if column in rows[0]), None)
        if nullable_column:
            for row in rows[: max(1, len(rows) // 20)]:
                row[nullable_column] = ""
            events.append(FailureEvent("schema_drift_NULLABILITY_CHANGED", table, nullable_column, max(1, len(rows) // 20)))

        for index, row in enumerate(rows):
            if index % 2 == 0:
                data[table][index] = {key: row[key] for key in reversed(list(row))}
        events.append(FailureEvent("schema_drift_COLUMN_ORDER_CHANGED", table, None, len(rows)))
        return events

    def apply(self, source: Dataset, selected_tables: set[str] | None = None) -> tuple[Dataset, list[FailureEvent]]:
        data = copy.deepcopy(source)
        selected = selected_tables or set(data)
        events: list[FailureEvent] = []

        for table in sorted(selected):
            if table not in data:
                continue
            rows = data[table]
            schema = self.spec.schemas[table]
            business_columns = [column for column in schema.columns if column not in {
                schema.primary_key,
                *AUDIT_COLUMNS,
                *TIME_HIERARCHY_COLUMNS,
                *SCD2_COLUMNS,
            }]
            if not business_columns:
                continue

            fk_columns = {fk.column for fk in schema.foreign_keys}
            drift_columns = [column for column in business_columns if column not in fk_columns]
            events.extend(self._schema_drift(data, table, drift_columns))

            event = self._mutate(data, table, "null_values", business_columns[0], "")
            if not event:
                event = self._mutate(data, table, "nulls", business_columns[0], "")
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
                events.append(FailureEvent("duplicate_records", table, schema.primary_key, len(duplicate_indices)))

            missing_indices = self._indices(rows, self.rates.get("missing_records", 0))
            for index in sorted(missing_indices, reverse=True):
                rows.pop(index)
            if missing_indices:
                events.append(FailureEvent("missing_records", table, schema.primary_key, len(missing_indices)))

        return data, events
