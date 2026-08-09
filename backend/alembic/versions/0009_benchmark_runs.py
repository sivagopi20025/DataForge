from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0009_benchmark_runs"
down_revision = "0008_benchmarking_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "benchmark_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("benchmark_id", sa.String(length=36), nullable=False),
        sa.Column("benchmark_version", sa.String(length=40), nullable=False),
        sa.Column("domain", sa.String(length=80), nullable=False),
        sa.Column("scenario_id", sa.String(length=255), nullable=False),
        sa.Column("scenario_run_id", sa.String(length=36), nullable=True),
        sa.Column("generation_job_id", sa.String(length=36), nullable=True),
        sa.Column("evaluation_run_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=60), nullable=False),
        sa.Column("status_reason", sa.Text(), nullable=True),
        sa.Column("detector_mode", sa.String(length=60), nullable=False),
        sa.Column("detector_status", sa.String(length=60), nullable=False),
        sa.Column("detector_name", sa.String(length=255), nullable=True),
        sa.Column("detector_version", sa.String(length=120), nullable=True),
        sa.Column("detector_output_artifact", sa.String(length=1000), nullable=True),
        sa.Column("artifact_manifest_json", sa.Text(), nullable=False),
        sa.Column("snapshot_json", sa.Text(), nullable=False),
        sa.Column("metrics_json", sa.Text(), nullable=True),
        sa.Column("acceptance_json", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        sa.Column("request_fingerprint", sa.String(length=128), nullable=True),
        sa.Column("result", sa.String(length=40), nullable=True),
        sa.Column("retain_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    for column in ("benchmark_id", "domain", "scenario_id", "scenario_run_id", "generation_job_id", "evaluation_run_id", "status", "idempotency_key", "result"):
        op.create_index(f"ix_benchmark_runs_{column}", "benchmark_runs", [column])


def downgrade() -> None:
    for column in reversed(("benchmark_id", "domain", "scenario_id", "scenario_run_id", "generation_job_id", "evaluation_run_id", "status", "idempotency_key", "result")):
        op.drop_index(f"ix_benchmark_runs_{column}", table_name="benchmark_runs")
    op.drop_table("benchmark_runs")
