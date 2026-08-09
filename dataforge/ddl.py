from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

from .model import DomainSpec, ForeignKey, TableSchema


SUPPORTED_DATABASE_TYPES = ("postgresql", "mssql", "mysql")


@dataclass(frozen=True)
class DDLPackage:
    path: Path
    file_name: str
    database_type: str


def generate_ddl_package(
    *,
    output_dir: Path,
    domain: str,
    spec: DomainSpec,
    selected_tables: set[str],
    database_type: str,
) -> DDLPackage:
    normalized_database = normalize_database_type(database_type)
    ordered_tables = [table for table in spec.schemas if table in selected_tables]
    if not ordered_tables:
        raise ValueError("At least one table is required for database DDL output")

    schema_name = _identifier(f"dataforge_{domain}")
    statements = {
        "ddl/schema.sql": _schema_sql(schema_name, normalized_database),
        "ddl/tables.sql": _tables_sql(schema_name, spec, ordered_tables, normalized_database),
        "ddl/indexes.sql": _indexes_sql(schema_name, spec, ordered_tables, normalized_database),
        "ddl/constraints.sql": _constraints_sql(schema_name, spec, ordered_tables, normalized_database),
        "ddl/foreign_keys.sql": _foreign_keys_sql(schema_name, spec, ordered_tables, normalized_database),
    }

    package_name = f"{domain}_{normalized_database}_ddl.zip"
    package_path = output_dir / package_name
    package_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(package_path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for arcname, content in statements.items():
            archive.writestr(arcname, content)
    return DDLPackage(path=package_path, file_name=package_name, database_type=normalized_database)


def normalize_database_type(database_type: str) -> str:
    normalized = database_type.strip().lower().replace("-", "_")
    aliases = {"postgres": "postgresql", "sqlserver": "mssql", "sql_server": "mssql", "microsoft_sql_server": "mssql"}
    normalized = aliases.get(normalized, normalized)
    if normalized not in SUPPORTED_DATABASE_TYPES:
        raise ValueError(f"Unsupported database type: {database_type}")
    return normalized


def _schema_sql(schema_name: str, database_type: str) -> str:
    if database_type == "postgresql":
        return f"CREATE SCHEMA IF NOT EXISTS {_quote(schema_name, database_type)};\nSET search_path TO {_quote(schema_name, database_type)};\n"
    if database_type == "mssql":
        return f"IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = N'{schema_name}') EXEC('CREATE SCHEMA {_quote(schema_name, database_type)}');\nGO\n"
    return f"CREATE DATABASE IF NOT EXISTS {_quote(schema_name, database_type)};\nUSE {_quote(schema_name, database_type)};\n"


def _tables_sql(schema_name: str, spec: DomainSpec, tables: list[str], database_type: str) -> str:
    chunks = []
    for table in tables:
        schema = spec.schemas[table]
        column_lines = []
        for column in schema.columns:
            column_type = _column_type(column, schema, database_type)
            nullable = "" if column == schema.primary_key else " NULL"
            column_lines.append(f"    {_quote(column, database_type)} {column_type}{nullable}")
        column_lines.append(f"    CONSTRAINT {_quote(_constraint_name('pk', table, schema.primary_key), database_type)} PRIMARY KEY ({_quote(schema.primary_key, database_type)})")
        chunks.append(f"CREATE TABLE {_table_name(schema_name, table, database_type)} (\n" + ",\n".join(column_lines) + "\n);")
        if database_type == "mssql":
            chunks.append("GO")
    return "\n\n".join(chunks) + "\n"


def _indexes_sql(schema_name: str, spec: DomainSpec, tables: list[str], database_type: str) -> str:
    selected = set(tables)
    lines = []
    for table in tables:
        schema = spec.schemas[table]
        index_columns = {fk.column for fk in schema.foreign_keys if fk.parent_table in selected}
        timestamp = spec.timestamp_sources.get(table)
        if timestamp and timestamp in schema.columns:
            index_columns.add(timestamp)
        for column in schema.columns:
            if _is_business_identifier(column):
                index_columns.add(column)
        for column in sorted(index_columns):
            if column == schema.primary_key:
                continue
            lines.append(f"CREATE INDEX {_quote(_constraint_name('ix', table, column), database_type)} ON {_table_name(schema_name, table, database_type)} ({_quote(column, database_type)});")
            if database_type == "mssql":
                lines.append("GO")
    return ("\n".join(lines) if lines else "-- No secondary indexes generated for the selected tables.") + "\n"


def _constraints_sql(schema_name: str, spec: DomainSpec, tables: list[str], database_type: str) -> str:
    lines = []
    for table in tables:
        schema = spec.schemas[table]
        nullable_columns = {fk.column for fk in schema.foreign_keys if fk.nullable}
        for column in schema.columns:
            if column in nullable_columns or column in {"effective_end_ts", "parent_category_id"}:
                continue
            if column == schema.primary_key:
                continue
            lines.extend(_not_null_sql(schema_name, table, column, database_type))

        for column in schema.columns:
            if _is_unique_identifier(column):
                lines.append(_unique_sql(schema_name, table, column, database_type))
                if database_type == "mssql":
                    lines.append("GO")
            if _is_check_column(column):
                check = _check_sql(schema_name, table, column, database_type)
                if check:
                    lines.append(check)
                    if database_type == "mssql":
                        lines.append("GO")
    return ("\n".join(lines) if lines else "-- No non-FK constraints generated for the selected tables.") + "\n"


def _foreign_keys_sql(schema_name: str, spec: DomainSpec, tables: list[str], database_type: str) -> str:
    selected = set(tables)
    lines = []
    for table in tables:
        schema = spec.schemas[table]
        for fk in schema.foreign_keys:
            if fk.parent_table not in selected:
                continue
            lines.append(_foreign_key_sql(schema_name, table, fk, database_type))
            if database_type == "mssql":
                lines.append("GO")
    return ("\n".join(lines) if lines else "-- No foreign keys generated for the selected tables.") + "\n"


def _foreign_key_sql(schema_name: str, table: str, fk: ForeignKey, database_type: str) -> str:
    return (
        f"ALTER TABLE {_table_name(schema_name, table, database_type)} ADD CONSTRAINT {_quote(_constraint_name('fk', table, fk.column), database_type)} "
        f"FOREIGN KEY ({_quote(fk.column, database_type)}) REFERENCES {_table_name(schema_name, fk.parent_table, database_type)} ({_quote(fk.parent_column, database_type)});"
    )


def _not_null_sql(schema_name: str, table: str, column: str, database_type: str) -> list[str]:
    if database_type == "postgresql":
        return [f"ALTER TABLE {_table_name(schema_name, table, database_type)} ALTER COLUMN {_quote(column, database_type)} SET NOT NULL;"]
    if database_type == "mssql":
        # SQL Server requires the type when altering nullability.
        column_type = _column_type(column, TableSchema(primary_key="", columns=()), database_type)
        return [f"ALTER TABLE {_table_name(schema_name, table, database_type)} ALTER COLUMN {_quote(column, database_type)} {column_type} NOT NULL;", "GO"]
    return [f"ALTER TABLE {_table_name(schema_name, table, database_type)} MODIFY COLUMN {_quote(column, database_type)} {_column_type(column, TableSchema(primary_key='', columns=()), database_type)} NOT NULL;"]


def _unique_sql(schema_name: str, table: str, column: str, database_type: str) -> str:
    return f"ALTER TABLE {_table_name(schema_name, table, database_type)} ADD CONSTRAINT {_quote(_constraint_name('uq', table, column), database_type)} UNIQUE ({_quote(column, database_type)});"


def _check_sql(schema_name: str, table: str, column: str, database_type: str) -> str | None:
    quoted_column = _quote(column, database_type)
    if column in {"rating", "seller_rating", "store_rating"}:
        expression = f"{quoted_column} >= 0 AND {quoted_column} <= 5"
    elif column.endswith("_amount") or column.endswith("_price") or column.endswith("_cost") or column in {"amount_paid", "total_fee", "refund_amount", "payment_amount", "available_quantity", "quantity", "duration_seconds", "affected_users"}:
        expression = f"{quoted_column} >= 0"
    elif column in {"attendance_percentage", "pass_percentage"}:
        expression = f"{quoted_column} >= 0 AND {quoted_column} <= 100"
    elif column.endswith("_flag") or column in {"active_flag", "is_deleted", "is_current"}:
        return None
    else:
        return None
    return f"ALTER TABLE {_table_name(schema_name, table, database_type)} ADD CONSTRAINT {_quote(_constraint_name('ck', table, column), database_type)} CHECK ({expression});"


def _column_type(column: str, schema: TableSchema, database_type: str) -> str:
    lower = column.lower()
    if lower.endswith("_ts") or lower.endswith("_time") or lower.endswith("_at") or lower in {"transaction_ts", "source_ts", "ingestion_ts", "updated_ts"}:
        return {"postgresql": "TIMESTAMP", "mssql": "DATETIME2", "mysql": "DATETIME"}[database_type]
    if lower.endswith("_date") or lower in {"dob", "birth_date", "due_date", "payment_date", "submitted_date"}:
        return "DATE"
    if lower.endswith("_flag") or lower in {"active_flag", "is_deleted", "is_current", "pass_flag", "roaming_enabled"}:
        return {"postgresql": "BOOLEAN", "mssql": "BIT", "mysql": "BOOLEAN"}[database_type]
    if lower.endswith("_amount") or lower.endswith("_price") or lower.endswith("_cost") or lower.endswith("_fee") or lower.endswith("_charges") or lower in {
        "taxes",
        "line_total",
        "total",
        "unit_cost",
        "selling_price",
        "monthly_fee",
        "data_used_mb",
        "marks_obtained",
        "maximum_marks",
        "discount_value",
        "attendance_percentage",
        "seller_rating",
        "store_rating",
        "rating",
    }:
        return {"postgresql": "NUMERIC(12,2)", "mssql": "DECIMAL(12,2)", "mysql": "DECIMAL(12,2)"}[database_type]
    if lower.endswith("_id") or lower == schema.primary_key or lower in {"business_key", "correlation_id", "event_id"}:
        return {"postgresql": "VARCHAR(64)", "mssql": "NVARCHAR(64)", "mysql": "VARCHAR(64)"}[database_type]
    if lower.endswith("_count") or lower.endswith("_quantity") or lower.endswith("_year") or lower.endswith("_days") or lower.endswith("_minutes") or lower.endswith("_seconds") or lower in {
        "quantity",
        "available_quantity",
        "capacity",
        "duration_years",
        "credits_required",
        "credit_hours",
        "semester",
        "category_level",
        "record_version",
        "transaction_hour",
        "transaction_day",
        "transaction_week",
        "transaction_month",
        "transaction_quarter",
        "transaction_year",
        "affected_users",
    }:
        return "INTEGER" if database_type == "postgresql" else "INT"
    if lower.endswith("_hash") or lower.endswith("_text") or lower in {"payload", "before_value", "after_value", "description", "issue_description", "review_text", "resolution_summary"}:
        return {"postgresql": "TEXT", "mssql": "NVARCHAR(MAX)", "mysql": "TEXT"}[database_type]
    length = 255
    if lower in {"email", "billing_email"}:
        length = 320
    elif lower.endswith("_number") or lower.endswith("_reference") or lower in {"sku", "npi_number", "iccid", "imsi", "imei", "tracking_number"}:
        length = 120
    return {"postgresql": f"VARCHAR({length})", "mssql": f"NVARCHAR({length})", "mysql": f"VARCHAR({length})"}[database_type]


def _table_name(schema_name: str, table: str, database_type: str) -> str:
    quoted_table = _quote(table, database_type)
    if database_type == "mysql":
        return quoted_table
    return f"{_quote(schema_name, database_type)}.{quoted_table}"


def _quote(identifier: str, database_type: str) -> str:
    safe = _identifier(identifier)
    if database_type == "mysql":
        return f"`{safe}`"
    if database_type == "mssql":
        return f"[{safe}]"
    return f'"{safe}"'


def _identifier(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_]", "_", value.strip().lower())
    return normalized.strip("_") or "dataforge"


def _constraint_name(prefix: str, table: str, column: str) -> str:
    return _identifier(f"{prefix}_{table}_{column}")[:120]


def _is_business_identifier(column: str) -> bool:
    return column in {
        "email",
        "sku",
        "order_number",
        "invoice_id",
        "transaction_reference",
        "claim_id",
        "policy_number",
        "account_number",
        "phone_number",
        "tracking_number",
        "course_code",
        "department_code",
        "tower_code",
    } or column.endswith("_number") or column.endswith("_reference")


def _is_unique_identifier(column: str) -> bool:
    return column in {"email", "sku", "order_number", "account_number", "transaction_reference", "tracking_number", "imei", "iccid", "imsi"}


def _is_check_column(column: str) -> bool:
    return column in {
        "rating",
        "seller_rating",
        "store_rating",
        "attendance_percentage",
        "pass_percentage",
        "amount_paid",
        "total_fee",
        "refund_amount",
        "payment_amount",
        "available_quantity",
        "quantity",
        "duration_seconds",
        "affected_users",
    } or column.endswith("_amount") or column.endswith("_price") or column.endswith("_cost")
