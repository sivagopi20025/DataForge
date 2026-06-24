from datetime import datetime, timezone

from backend.app.repositories import DatasetRunRepository, GeneratedFileRepository, GenerationJobRepository, UserRepository


def test_repositories_create_user_run_and_counts(db_session, tmp_path):
    users = UserRepository(db_session)
    runs = DatasetRunRepository(db_session)
    files = GeneratedFileRepository(db_session)

    user = users.get_or_create("repo@example.test", "pro")
    run = runs.create(
        user_id=user.id,
        domain="retail",
        load_type="bulk",
        file_format="csv",
        record_count=10,
        status="completed",
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
    )
    path = tmp_path / "sample.csv"
    path.write_text("a,b\n1,2\n")
    files.create(run_id=run.id, path=path, file_format="csv")
    db_session.commit()

    assert users.count() == 1
    assert runs.count() == 1
    assert files.count() == 1
    assert runs.get(run.id).generated_files[0].file_name == "sample.csv"


def test_generation_job_repository_tracks_queued_running_completed_and_failed(db_session):
    jobs = GenerationJobRepository(db_session)
    queued = jobs.create(request_payload={"domain": "retail", "records": 5})
    db_session.commit()

    assert queued.status == "queued"
    running = jobs.mark_running(queued, datetime.now(timezone.utc))
    assert running.status == "running"

    completed = jobs.mark_completed(running, run_id="run-123", completed_at=datetime.now(timezone.utc))
    assert completed.status == "completed"
    assert completed.run_id == "run-123"

    failed = jobs.create(request_payload={"domain": "unknown"})
    jobs.mark_failed(failed, error_message="Unsupported domain: unknown", completed_at=datetime.now(timezone.utc))
    db_session.commit()

    assert jobs.get(failed.id).status == "failed"
    assert "Unsupported domain" in jobs.get(failed.id).error_message
