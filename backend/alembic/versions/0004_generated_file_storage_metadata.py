from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0004_generated_file_storage_metadata"
down_revision = "0003_generation_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("generated_files", sa.Column("storage_backend", sa.String(length=50), nullable=False, server_default="local"))
    op.add_column("generated_files", sa.Column("object_key", sa.String(length=1000), nullable=False, server_default=""))
    op.add_column("generated_files", sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"))
    op.add_column(
        "generated_files",
        sa.Column("content_type", sa.String(length=120), nullable=False, server_default="application/octet-stream"),
    )


def downgrade() -> None:
    op.drop_column("generated_files", "content_type")
    op.drop_column("generated_files", "size_bytes")
    op.drop_column("generated_files", "object_key")
    op.drop_column("generated_files", "storage_backend")
