from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0001_backend_foundation"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False, unique=True),
        sa.Column("plan", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_table(
        "dataset_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("domain", sa.String(length=80), nullable=False),
        sa.Column("load_type", sa.String(length=80), nullable=False),
        sa.Column("format", sa.String(length=80), nullable=False),
        sa.Column("record_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_dataset_runs_user_id", "dataset_runs", ["user_id"])
    op.create_index("ix_dataset_runs_domain", "dataset_runs", ["domain"])
    op.create_index("ix_dataset_runs_load_type", "dataset_runs", ["load_type"])
    op.create_index("ix_dataset_runs_format", "dataset_runs", ["format"])
    op.create_index("ix_dataset_runs_status", "dataset_runs", ["status"])
    op.create_table(
        "generated_files",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("run_id", sa.String(length=36), sa.ForeignKey("dataset_runs.id"), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_path", sa.String(length=1000), nullable=False),
        sa.Column("file_format", sa.String(length=50), nullable=False),
        sa.Column("file_size_mb", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_generated_files_run_id", "generated_files", ["run_id"])
    op.create_index("ix_generated_files_file_format", "generated_files", ["file_format"])
    op.create_table(
        "issue_manifests",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("run_id", sa.String(length=36), sa.ForeignKey("dataset_runs.id"), nullable=False),
        sa.Column("issue_type", sa.String(length=120), nullable=False),
        sa.Column("issue_count", sa.Integer(), nullable=False),
        sa.Column("issue_percentage", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_issue_manifests_run_id", "issue_manifests", ["run_id"])
    op.create_index("ix_issue_manifests_issue_type", "issue_manifests", ["issue_type"])
    op.create_table(
        "validation_results",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("run_id", sa.String(length=36), sa.ForeignKey("dataset_runs.id"), nullable=False),
        sa.Column("validation_name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("expected_value", sa.Text(), nullable=True),
        sa.Column("actual_value", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_validation_results_run_id", "validation_results", ["run_id"])
    op.create_index("ix_validation_results_status", "validation_results", ["status"])
    op.create_table(
        "admin_metrics",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("metric_name", sa.String(length=255), nullable=False),
        sa.Column("metric_value", sa.Float(), nullable=False),
        sa.Column("metric_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_admin_metrics_metric_name", "admin_metrics", ["metric_name"])
    op.create_index("ix_admin_metrics_metric_date", "admin_metrics", ["metric_date"])


def downgrade() -> None:
    op.drop_table("admin_metrics")
    op.drop_table("validation_results")
    op.drop_table("issue_manifests")
    op.drop_table("generated_files")
    op.drop_table("dataset_runs")
    op.drop_table("users")
