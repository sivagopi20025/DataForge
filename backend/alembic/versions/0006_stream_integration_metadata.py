from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0006_stream_integration_metadata"
down_revision = "0005_streaming_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("stream_sessions", sa.Column("stream_token_hash", sa.String(length=128), nullable=True))
    op.add_column("stream_sessions", sa.Column("stream_token_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("stream_sessions", sa.Column("webhook_url", sa.Text(), nullable=True))
    op.add_column("stream_sessions", sa.Column("webhook_secret_hash", sa.String(length=128), nullable=True))
    op.add_column("stream_sessions", sa.Column("webhook_delivery_summary", sa.Text(), nullable=False, server_default="{}"))
    op.create_index("ix_stream_sessions_stream_token_hash", "stream_sessions", ["stream_token_hash"])


def downgrade() -> None:
    op.drop_index("ix_stream_sessions_stream_token_hash", table_name="stream_sessions")
    op.drop_column("stream_sessions", "webhook_delivery_summary")
    op.drop_column("stream_sessions", "webhook_secret_hash")
    op.drop_column("stream_sessions", "webhook_url")
    op.drop_column("stream_sessions", "stream_token_expires_at")
    op.drop_column("stream_sessions", "stream_token_hash")
