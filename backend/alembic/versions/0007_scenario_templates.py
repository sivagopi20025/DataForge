from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0007_scenario_templates"
down_revision = "0006_stream_integration_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scenario_templates",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("domain", sa.String(length=80), nullable=False),
        sa.Column("scenario_id", sa.String(length=255), nullable=False),
        sa.Column("records", sa.Integer(), nullable=False),
        sa.Column("output_format", sa.String(length=40), nullable=False),
        sa.Column("severity", sa.String(length=40), nullable=False),
        sa.Column("seed_behavior", sa.String(length=40), nullable=False),
        sa.Column("failure_plan_json", sa.Text(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_scenario_templates_name", "scenario_templates", ["name"])
    op.create_index("ix_scenario_templates_domain", "scenario_templates", ["domain"])
    op.create_index("ix_scenario_templates_scenario_id", "scenario_templates", ["scenario_id"])


def downgrade() -> None:
    op.drop_index("ix_scenario_templates_scenario_id", table_name="scenario_templates")
    op.drop_index("ix_scenario_templates_domain", table_name="scenario_templates")
    op.drop_index("ix_scenario_templates_name", table_name="scenario_templates")
    op.drop_table("scenario_templates")
