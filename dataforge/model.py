from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


Row = dict[str, Any]
Dataset = dict[str, list[Row]]
BusinessRule = Callable[[Dataset], list[dict[str, Any]]]


@dataclass(frozen=True)
class ForeignKey:
    column: str
    parent_table: str
    parent_column: str
    nullable: bool = False


@dataclass(frozen=True)
class TableSchema:
    primary_key: str
    columns: tuple[str, ...]
    foreign_keys: tuple[ForeignKey, ...] = ()


@dataclass(frozen=True)
class EventDefinition:
    name: str
    table: str
    event_type: str
    key_column: str
    timestamp_column: str | None = None
    sample_every: int | None = None


@dataclass(frozen=True)
class DomainSpec:
    name: str
    source_system: str
    schemas: dict[str, TableSchema]
    fact_tables: set[str]
    dimension_tables: set[str]
    timestamp_sources: dict[str, str]
    date_columns: dict[str, str]
    numeric_columns: dict[str, str]
    type_mismatch_columns: dict[str, str]
    event_definitions: tuple[EventDefinition, ...] = ()
    cdc_tables: tuple[str, ...] = ()
    business_rules: tuple[BusinessRule, ...] = ()


@dataclass
class FailureEvent:
    failure_type: str
    table: str
    column: str | None
    count: int
    details: dict[str, Any] = field(default_factory=dict)


AUDIT_COLUMNS = (
    "created_ts", "updated_ts", "source_ts", "ingestion_ts", "batch_id",
    "load_id", "record_version", "is_deleted", "source_system", "record_hash",
)
TIME_HIERARCHY_COLUMNS = (
    "transaction_ts", "transaction_date", "transaction_hour", "transaction_day",
    "transaction_week", "transaction_month", "transaction_quarter", "transaction_year",
)
SCD2_COLUMNS = ("effective_start_ts", "effective_end_ts", "is_current")


def with_enterprise_columns(
    schemas: dict[str, TableSchema],
    fact_tables: set[str],
    dimension_tables: set[str],
) -> dict[str, TableSchema]:
    enriched: dict[str, TableSchema] = {}
    for table, schema in schemas.items():
        extra = tuple(column for column in AUDIT_COLUMNS if column != "record_hash")
        if table in fact_tables:
            extra += TIME_HIERARCHY_COLUMNS
        if table in dimension_tables:
            extra += SCD2_COLUMNS
        extra += ("record_hash",)
        deduped_extra = tuple(column for column in extra if column not in schema.columns)
        enriched[table] = TableSchema(schema.primary_key, schema.columns + deduped_extra, schema.foreign_keys)
    return enriched


# Compatibility exports for the original Retail-first implementation.
from .domains.retail.schemas import RETAIL_SPEC  # noqa: E402

SCHEMAS = RETAIL_SPEC.schemas
FACT_TABLES = RETAIL_SPEC.fact_tables
DIMENSION_TABLES = RETAIL_SPEC.dimension_tables
