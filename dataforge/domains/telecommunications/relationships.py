from __future__ import annotations

from .schemas import TELECOMMUNICATIONS_SPEC

RELATIONSHIPS = {
    table: tuple((fk.column, fk.parent_table, fk.parent_column) for fk in schema.foreign_keys)
    for table, schema in TELECOMMUNICATIONS_SPEC.schemas.items()
}
