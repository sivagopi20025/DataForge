from __future__ import annotations

from .schemas import BASE_SCHEMAS

RELATIONSHIPS = tuple(
    (table, fk.column, fk.parent_table, fk.parent_column)
    for table, schema in BASE_SCHEMAS.items()
    for fk in schema.foreign_keys
)
