from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0002_validation_quality_score"
down_revision = "0001_backend_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("validation_results", sa.Column("quality_score", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("validation_results", "quality_score")
