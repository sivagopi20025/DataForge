from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0005_streaming_sessions"
down_revision = "0004_file_storage_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stream_sessions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("domain", sa.String(length=80), nullable=False),
        sa.Column("event_types", sa.Text(), nullable=False),
        sa.Column("events_per_second", sa.Integer(), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("format", sa.String(length=20), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("failure_injections", sa.Text(), nullable=False),
        sa.Column("events_generated", sa.Integer(), nullable=False),
        sa.Column("events_failed", sa.Integer(), nullable=False),
        sa.Column("failure_summary", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("estimated_end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_stream_sessions_domain", "stream_sessions", ["domain"])
    op.create_index("ix_stream_sessions_status", "stream_sessions", ["status"])

    op.create_table(
        "stream_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("stream_id", sa.String(length=36), sa.ForeignKey("stream_sessions.id"), nullable=False),
        sa.Column("event_id", sa.String(length=80), nullable=False),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("domain", sa.String(length=80), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("correlation_id", sa.String(length=80), nullable=False),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ingestion_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("injected_issues", sa.Text(), nullable=False),
        sa.Column("raw_event", sa.Text(), nullable=True),
        sa.Column("is_malformed", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_stream_events_stream_id", "stream_events", ["stream_id"])
    op.create_index("ix_stream_events_event_id", "stream_events", ["event_id"])
    op.create_index("ix_stream_events_event_type", "stream_events", ["event_type"])
    op.create_index("ix_stream_events_domain", "stream_events", ["domain"])
    op.create_index("ix_stream_events_sequence_number", "stream_events", ["sequence_number"])
    op.create_index("ix_stream_events_correlation_id", "stream_events", ["correlation_id"])


def downgrade() -> None:
    op.drop_table("stream_events")
    op.drop_table("stream_sessions")
