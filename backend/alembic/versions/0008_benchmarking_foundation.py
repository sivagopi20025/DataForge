from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0008_benchmarking_foundation"
down_revision = "0007_scenario_templates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "benchmark_definitions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("version", sa.String(length=40), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("domain", sa.String(length=80), nullable=False),
        sa.Column("scenario_id", sa.String(length=255), nullable=False),
        sa.Column("scenario_template_id", sa.String(length=36), nullable=True),
        sa.Column("records", sa.Integer(), nullable=False),
        sa.Column("output_format", sa.String(length=40), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=False),
        sa.Column("failure_plan_json", sa.Text(), nullable=False),
        sa.Column("evaluation_unit", sa.String(length=80), nullable=False),
        sa.Column("thresholds_json", sa.Text(), nullable=False),
        sa.Column("snapshot_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_benchmark_definitions_name", "benchmark_definitions", ["name"])
    op.create_index("ix_benchmark_definitions_slug", "benchmark_definitions", ["slug"])
    op.create_index("ix_benchmark_definitions_domain", "benchmark_definitions", ["domain"])
    op.create_index("ix_benchmark_definitions_scenario_id", "benchmark_definitions", ["scenario_id"])
    op.create_index("ix_benchmark_definitions_scenario_template_id", "benchmark_definitions", ["scenario_template_id"])

    op.create_table(
        "evaluation_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("scenario_run_id", sa.String(length=36), nullable=False),
        sa.Column("benchmark_id", sa.String(length=36), nullable=True),
        sa.Column("benchmark_version", sa.String(length=40), nullable=True),
        sa.Column("detector_name", sa.String(length=255), nullable=False),
        sa.Column("detector_version", sa.String(length=120), nullable=True),
        sa.Column("detector_output_format", sa.String(length=40), nullable=False),
        sa.Column("detector_output_checksum", sa.String(length=128), nullable=True),
        sa.Column("detector_output_artifact", sa.String(length=1000), nullable=True),
        sa.Column("result_artifact", sa.String(length=1000), nullable=True),
        sa.Column("metrics_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_evaluation_runs_scenario_run_id", "evaluation_runs", ["scenario_run_id"])
    op.create_index("ix_evaluation_runs_benchmark_id", "evaluation_runs", ["benchmark_id"])
    op.create_index("ix_evaluation_runs_status", "evaluation_runs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_evaluation_runs_status", table_name="evaluation_runs")
    op.drop_index("ix_evaluation_runs_benchmark_id", table_name="evaluation_runs")
    op.drop_index("ix_evaluation_runs_scenario_run_id", table_name="evaluation_runs")
    op.drop_table("evaluation_runs")
    op.drop_index("ix_benchmark_definitions_scenario_template_id", table_name="benchmark_definitions")
    op.drop_index("ix_benchmark_definitions_scenario_id", table_name="benchmark_definitions")
    op.drop_index("ix_benchmark_definitions_domain", table_name="benchmark_definitions")
    op.drop_index("ix_benchmark_definitions_slug", table_name="benchmark_definitions")
    op.drop_index("ix_benchmark_definitions_name", table_name="benchmark_definitions")
    op.drop_table("benchmark_definitions")
