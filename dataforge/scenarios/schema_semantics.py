from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from dataforge.domains import DOMAIN_SPECS
from dataforge.model import DomainSpec, ForeignKey, TableSchema


GENERIC_COLUMN_BLOCKERS = {
    "amount",
    "actual_amount",
    "expected_amount",
    "event_timestamp",
    "reason_code",
    "scenario_status_code",
    "reconciliation_group_id",
    "status",
    "risk_score",
    "idempotency_key",
}

_TIMESTAMP_HINTS = (
    "event_timestamp",
    "event_time",
    "timestamp",
    "time",
    "date",
    "created_at",
    "created_date",
    "submitted",
    "processed",
    "approved",
    "settled",
    "shipped",
    "delivered",
    "opened",
    "closed",
    "detected",
    "scheduled",
    "due",
)

_AMOUNT_HINTS = (
    "amount",
    "total",
    "price",
    "cost",
    "balance",
    "value",
    "premium",
    "claim",
    "coverage",
    "settlement",
    "fee",
    "salary",
    "quantity",
)

_STATUS_HINTS = ("status", "active_flag")
_REASON_HINTS = ("reason", "code", "defect", "exception", "denial", "decline", "cancel")
_RISK_HINTS = ("risk", "rating", "score", "fraud")


@dataclass(frozen=True)
class ColumnSemantic:
    domain: str
    table: str
    column: str
    data_type: str
    semantic_role: str
    business_entity: str
    aliases: tuple[str, ...] = ()
    timestamp_role: str | None = None
    amount_role: str | None = None
    status_role: str | None = None
    identifier_role: str | None = None


@dataclass(frozen=True)
class ColumnResolution:
    requested_column: str
    resolved_column: str | None
    domain: str
    table: str
    semantic_role: str | None
    resolution_type: str
    ambiguity: tuple[str, ...] = ()
    reason: str | None = None

    @property
    def resolved(self) -> bool:
        return self.resolved_column is not None

    def model_dump(self) -> dict[str, Any]:
        return {
            "requested_column": self.requested_column,
            "resolved_column": self.resolved_column,
            "domain": self.domain,
            "table": self.table,
            "semantic_role": self.semantic_role,
            "resolution_type": self.resolution_type,
            "ambiguity": list(self.ambiguity),
            "reason": self.reason,
        }


def _business_entity(table: str) -> str:
    if table.endswith("ies"):
        return f"{table[:-3]}y"
    if table.endswith("s"):
        return table[:-1]
    return table


def _infer_data_type(column: str) -> str:
    lowered = column.lower()
    if lowered.startswith("is_") or lowered.endswith("_flag"):
        return "boolean"
    if any(hint in lowered for hint in _TIMESTAMP_HINTS):
        return "timestamp" if "time" in lowered or lowered.endswith("_ts") else "date"
    if any(hint in lowered for hint in _AMOUNT_HINTS) or lowered.endswith("_pct") or lowered.endswith("_percentage"):
        return "number"
    if lowered.endswith("_id") or lowered in {"id", "batch_id", "load_id", "record_hash"}:
        return "string"
    if lowered in {"record_version", "sequence_number", "capacity", "rating"}:
        return "number"
    return "string"


def _semantic_role(column: str, schema: TableSchema, fks: tuple[ForeignKey, ...]) -> str:
    lowered = column.lower()
    fk_columns = {fk.column for fk in fks}
    if column == schema.primary_key:
        return "entity_id"
    if column in fk_columns:
        return "parent_id"
    if _is_business_status_column(column):
        return "status"
    if _is_reason_column(column):
        return "reason"
    if any(hint in lowered for hint in _TIMESTAMP_HINTS):
        if "created" in lowered:
            return "created_time"
        if "updated" in lowered:
            return "updated_time"
        if "start" in lowered or "opened" in lowered or "submitted" in lowered:
            return "start_time"
        if "end" in lowered or "closed" in lowered or "delivered" in lowered or "settled" in lowered:
            return "end_time"
        return "event_time"
    if any(hint in lowered for hint in _AMOUNT_HINTS):
        if "expected" in lowered or "planned" in lowered:
            return "expected_value"
        if "actual" in lowered:
            return "actual_value"
        if "quantity" in lowered or lowered.endswith("_qty"):
            return "quantity"
        return "amount"
    if any(hint in lowered for hint in ("country", "state", "city", "region", "latitude", "longitude", "postal")):
        return "location"
    if any(hint in lowered for hint in ("type", "category", "segment", "specialty", "department")):
        return "category"
    if any(hint in lowered for hint in ("sequence", "version")):
        return "sequence"
    if "policy" in lowered:
        return "policy_reference"
    return "attribute"


def build_domain_column_semantics() -> dict[str, dict[str, list[ColumnSemantic]]]:
    inventory: dict[str, dict[str, list[ColumnSemantic]]] = {}
    for domain, spec in DOMAIN_SPECS.items():
        inventory[domain] = {}
        for table, schema in spec.schemas.items():
            rows: list[ColumnSemantic] = []
            for column in schema.columns:
                role = _semantic_role(column, schema, schema.foreign_keys)
                aliases = _aliases_for_column(column, role)
                rows.append(
                    ColumnSemantic(
                        domain=domain,
                        table=table,
                        column=column,
                        data_type=_infer_data_type(column),
                        semantic_role=role,
                        business_entity=_business_entity(table),
                        aliases=tuple(sorted(aliases)),
                        timestamp_role=role if role in {"event_time", "created_time", "updated_time", "start_time", "end_time"} else None,
                        amount_role=role if role in {"amount", "quantity", "expected_value", "actual_value", "threshold"} else None,
                        status_role=role if role == "status" else None,
                        identifier_role=role if role in {"entity_id", "parent_id", "grouping_key"} else None,
                    )
                )
            inventory[domain][table] = rows
    return inventory


def _aliases_for_column(column: str, role: str) -> set[str]:
    aliases: set[str] = set()
    lowered = column.lower()
    if role in {"amount", "quantity", "expected_value", "actual_value"}:
        aliases.update({"amount", "expected_amount", "actual_amount"})
    if role in {"event_time", "created_time", "updated_time", "start_time", "end_time"}:
        aliases.add("event_timestamp")
    if role == "status":
        aliases.update({"status", "scenario_status_code"})
    if role == "reason" or any(hint in lowered for hint in _REASON_HINTS):
        aliases.add("reason_code")
    if role in {"entity_id", "parent_id"}:
        aliases.add("reconciliation_group_id")
    if any(hint in lowered for hint in _RISK_HINTS):
        aliases.add("risk_score")
    return aliases


class ColumnSemanticResolver:
    """Resolve generic scenario placeholders to existing domain-native columns.

    The resolver deliberately keeps idempotency keys unresolved unless a real column
    exists. An idempotency key is a business/API concept; mapping it to a primary key
    would make retry scenarios look executable while changing their meaning.
    """

    def resolve(self, domain: str, table: str, requested_column: str) -> ColumnResolution:
        spec = DOMAIN_SPECS.get(domain)
        if not spec:
            return ColumnResolution(requested_column, None, domain, table, None, "unknown_domain")
        schema = spec.schemas.get(table)
        if not schema:
            return ColumnResolution(requested_column, None, domain, table, None, "unknown_table")
        if requested_column in schema.columns:
            return ColumnResolution(requested_column, requested_column, domain, table, _semantic_role(requested_column, schema, schema.foreign_keys), "exact")
        if requested_column == "idempotency_key":
            return ColumnResolution(requested_column, None, domain, table, "idempotency", "true_schema_gap", reason="No domain-native idempotency key exists on this table.")

        candidates = self._candidates_for(spec, table, requested_column)
        if not candidates:
            return ColumnResolution(requested_column, None, domain, table, None, "unresolved", reason="No semantically equivalent existing column was found.")

        resolved = candidates[0]
        return ColumnResolution(
            requested_column,
            resolved,
            domain,
            table,
            _semantic_role(resolved, schema, schema.foreign_keys),
            "semantic_alias" if requested_column != resolved else "exact",
            ambiguity=tuple(candidates[1:]),
            reason=f"{requested_column} maps to existing domain-native {table}.{resolved}.",
        )

    def resolve_for_scenario_tables(self, domain: str, tables: list[str], requested_column: str) -> ColumnResolution:
        for table in tables:
            resolution = self.resolve(domain, table, requested_column)
            if resolution.resolved:
                return resolution
        table = tables[0] if tables else ""
        return self.resolve(domain, table, requested_column)

    def missing_columns(self, domain: str, tables: list[str], required_columns: list[str]) -> list[str]:
        missing: list[str] = []
        for column in required_columns:
            resolution = self.resolve_for_scenario_tables(domain, tables, column)
            if not resolution.resolved:
                if not self._exists_anywhere(domain, column):
                    missing.append(column)
        return sorted(dict.fromkeys(missing))

    def normalize_parameters(self, domain: str, table: str, parameters: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(parameters)
        table_value = str(normalized.get("table") or table)
        schema = DOMAIN_SPECS.get(domain).schemas.get(table_value) if DOMAIN_SPECS.get(domain) else None
        if isinstance(normalized.get("id_column"), str) and schema:
            resolution = self.resolve(domain, table_value, normalized["id_column"])
            if resolution.resolved and resolution.semantic_role in {"entity_id", "parent_id"}:
                normalized["id_column"] = resolution.resolved_column
            elif normalized["id_column"] not in schema.columns:
                normalized["id_column"] = schema.primary_key
        for key in ("column", "status_column", "timestamp_column", "start_timestamp_column", "end_timestamp_column", "group_key"):
            if isinstance(normalized.get(key), str):
                resolution = self.resolve(domain, table_value, normalized[key])
                if resolution.resolved:
                    normalized[key] = resolution.resolved_column
        for key in ("columns", "group_keys", "group_by_columns"):
            if isinstance(normalized.get(key), list):
                mapped: list[Any] = []
                for value in normalized[key]:
                    if isinstance(value, str):
                        resolution = self.resolve(domain, table_value, value)
                        mapped.append(resolution.resolved_column if resolution.resolved else value)
                    else:
                        mapped.append(value)
                normalized[key] = list(dict.fromkeys(mapped))
        return normalized

    def _exists_anywhere(self, domain: str, column: str) -> bool:
        spec = DOMAIN_SPECS.get(domain)
        return bool(spec and any(column in schema.columns for schema in spec.schemas.values()))

    def _candidates_for(self, spec: DomainSpec, table: str, requested_column: str) -> list[str]:
        schema = spec.schemas[table]
        columns = list(schema.columns)
        if requested_column in {"amount", "expected_amount", "actual_amount"}:
            preferred = spec.numeric_columns.get(table)
            candidates = [preferred] if preferred and preferred in columns else []
            candidates.extend(column for column in columns if any(hint in column.lower() for hint in _AMOUNT_HINTS))
            return _dedupe(candidates)
        if requested_column == "event_timestamp":
            preferred = spec.timestamp_sources.get(table) or spec.date_columns.get(table)
            candidates = [preferred] if preferred and preferred in columns else []
            candidates.extend(column for column in columns if any(hint in column.lower() for hint in _TIMESTAMP_HINTS))
            return _dedupe(candidates)
        if requested_column in {"status", "scenario_status_code"}:
            return _dedupe(column for column in columns if _is_business_status_column(column))
        if requested_column == "reason_code":
            exact_reason = [column for column in columns if _is_reason_column(column)]
            return _dedupe(exact_reason)
        if requested_column == "reconciliation_group_id":
            candidates = [fk.column for fk in schema.foreign_keys]
            candidates.append(schema.primary_key)
            return _dedupe(candidates)
        if requested_column == "risk_score":
            return _dedupe(column for column in columns if any(hint in column.lower() for hint in _RISK_HINTS))
        return []


def _dedupe(values: Any) -> list[str]:
    return [value for value in dict.fromkeys(value for value in values if value)]


def _is_business_status_column(column: str) -> bool:
    lowered = column.lower()
    if lowered in {"state", "is_deleted", "is_current"}:
        return False
    return "status" in lowered or lowered == "active_flag" or lowered.endswith("_state")


def _is_reason_column(column: str) -> bool:
    lowered = column.lower()
    if any(hint in lowered for hint in ("reason", "exception", "denial", "decline", "cancel", "error", "defect", "hold")):
        return True
    return lowered.endswith("_code") and any(prefix in lowered for prefix in ("error", "defect", "reject", "denial", "decline", "exception"))


COLUMN_SEMANTIC_RESOLVER = ColumnSemanticResolver()
