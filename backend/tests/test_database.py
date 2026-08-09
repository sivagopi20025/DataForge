from sqlalchemy import inspect

from backend.app.db.base import Base


def test_database_metadata_contains_required_tables(db_session):
    inspector = inspect(db_session.bind)
    expected = {
        "users",
        "dataset_runs",
        "generated_files",
        "generation_jobs",
        "issue_manifests",
        "validation_results",
        "admin_metrics",
        "stream_sessions",
        "stream_events",
    }
    assert expected <= set(inspector.get_table_names())
    assert expected <= set(Base.metadata.tables)
