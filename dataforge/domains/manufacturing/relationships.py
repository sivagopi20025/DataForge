from __future__ import annotations

from .schemas import MANUFACTURING_SPEC

RELATIONSHIPS = {
    table: tuple((fk.column, fk.parent_table, fk.parent_column) for fk in schema.foreign_keys)
    for table, schema in MANUFACTURING_SPEC.schemas.items()
}
