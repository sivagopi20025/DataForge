from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.core.config import get_settings
from backend.app.core.rate_limit import rate_limiter
from backend.app.db.base import Base
from backend.app.db.session import get_db
from backend.app.main import create_app
from backend.app.models import DatasetRun, GeneratedFile, GenerationJob, User
from backend.app.services.retention import cleanup_expired_run_history, cleanup_generated_files, cleanup_stored_generated_files


def test_production_requires_api_key(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("DATAFORGE_API_KEY", raising=False)
    get_settings.cache_clear()

    try:
        with pytest.raises(RuntimeError, match="DATAFORGE_API_KEY is required"):
            create_app()
    finally:
        get_settings.cache_clear()


@pytest.mark.parametrize(
    "cors_origins, error",
    [
        ("", "CORS_ORIGINS must include"),
        ("*", "CORS_ORIGINS cannot include"),
        ("http://app.example.com", "CORS_ORIGINS must use exact https"),
    ],
)
def test_production_rejects_unsafe_cors_origins(monkeypatch, cors_origins, error):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATAFORGE_API_KEY", "secret-test-key")
    monkeypatch.setenv("CORS_ORIGINS", cors_origins)
    get_settings.cache_clear()

    try:
        with pytest.raises(RuntimeError, match=error):
            create_app()
    finally:
        get_settings.cache_clear()


def test_api_key_is_required_when_configured(tmp_path, monkeypatch):
    monkeypatch.setenv("DATAFORGE_API_KEY", "secret-test-key")
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "backend-output"))
    get_settings.cache_clear()
    engine = create_engine(f"sqlite:///{tmp_path / 'auth.db'}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db: Session = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app = create_app()
    app.state.SessionLocal = TestingSessionLocal
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        denied = client.post("/api/v1/generate", json={"domain": "retail", "records": 5})
        allowed = client.post("/api/v1/generate", headers={"X-API-Key": "secret-test-key"}, json={"domain": "retail", "records": 5})

    assert denied.status_code == 401
    assert allowed.status_code == 200
    Base.metadata.drop_all(bind=engine)
    get_settings.cache_clear()


def test_security_headers_are_added(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert "camera=()" in response.headers["permissions-policy"]


def test_generate_rejects_records_above_configured_limit(client, monkeypatch):
    monkeypatch.setenv("MAX_BATCH_RECORDS", "25")
    get_settings.cache_clear()

    response = client.post("/api/v1/generate", json={"domain": "retail", "records": 26})

    assert response.status_code == 422
    assert "records must be less than or equal to 25" in response.text
    get_settings.cache_clear()


def test_rate_limit_allows_requests_under_configured_limit(tmp_path, monkeypatch):
    monkeypatch.setenv("DATAFORGE_API_KEY", "secret-test-key")
    monkeypatch.setenv("RATE_LIMIT_REQUESTS", "2")
    monkeypatch.setenv("RATE_LIMIT_WINDOW_SECONDS", "60")
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "backend-output"))
    get_settings.cache_clear()
    rate_limiter.clear()
    engine = create_engine(f"sqlite:///{tmp_path / 'rate_allowed.db'}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db: Session = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app = create_app()
    app.state.SessionLocal = TestingSessionLocal
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        first = client.get("/api/v1/runs", headers={"X-API-Key": "secret-test-key"})
        second = client.get("/api/v1/runs", headers={"X-API-Key": "secret-test-key"})

    assert first.status_code == 200
    assert second.status_code == 200
    Base.metadata.drop_all(bind=engine)
    rate_limiter.clear()
    get_settings.cache_clear()


def test_rate_limit_blocks_requests_over_configured_limit(tmp_path, monkeypatch):
    monkeypatch.setenv("DATAFORGE_API_KEY", "secret-test-key")
    monkeypatch.setenv("RATE_LIMIT_REQUESTS", "1")
    monkeypatch.setenv("RATE_LIMIT_WINDOW_SECONDS", "60")
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "backend-output"))
    get_settings.cache_clear()
    rate_limiter.clear()
    engine = create_engine(f"sqlite:///{tmp_path / 'rate_blocked.db'}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db: Session = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app = create_app()
    app.state.SessionLocal = TestingSessionLocal
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        allowed = client.get("/api/v1/runs", headers={"X-API-Key": "secret-test-key"})
        blocked = client.get("/api/v1/runs", headers={"X-API-Key": "secret-test-key"})

    assert allowed.status_code == 200
    assert blocked.status_code == 429
    assert blocked.json()["code"] == "RATE_LIMIT_EXCEEDED"
    assert blocked.json()["error"] == "Rate limit exceeded"
    assert int(blocked.headers["Retry-After"]) > 0
    Base.metadata.drop_all(bind=engine)
    rate_limiter.clear()
    get_settings.cache_clear()


def test_cleanup_generated_files_dry_run_and_apply(tmp_path):
    old_run = tmp_path / "old-run"
    new_run = tmp_path / "new-run"
    old_run.mkdir()
    new_run.mkdir()
    (old_run / "data.json").write_text("old")
    (new_run / "data.json").write_text("new")
    old_timestamp = (datetime.now(timezone.utc) - timedelta(days=10)).timestamp()
    os.utime(old_run, (old_timestamp, old_timestamp))
    os.utime(old_run / "data.json", (old_timestamp, old_timestamp))

    dry_run = cleanup_generated_files(tmp_path, retention_days=7, dry_run=True)

    assert dry_run.scanned == 2
    assert dry_run.deleted == 1
    assert old_run.exists()
    applied = cleanup_generated_files(tmp_path, retention_days=7, dry_run=False)
    assert applied.deleted == 1
    assert not old_run.exists()
    assert new_run.exists()


def test_storage_aware_retention_deletes_local_generated_files(db_session, tmp_path):
    output_dir = tmp_path / "backend-output"
    old_file = output_dir / "old-run" / "customers.json"
    old_file.parent.mkdir(parents=True)
    old_file.write_text("old", encoding="utf-8")
    new_file = output_dir / "new-run" / "customers.json"
    new_file.parent.mkdir(parents=True)
    new_file.write_text("new", encoding="utf-8")
    user = User(email="retention@example.test", plan="free")
    db_session.add(user)
    db_session.flush()
    old_run = DatasetRun(
        user_id=user.id,
        domain="retail",
        load_type="bulk",
        format="json",
        record_count=1,
        status="completed",
        started_at=datetime.now(timezone.utc) - timedelta(days=10),
        completed_at=datetime.now(timezone.utc) - timedelta(days=10),
    )
    new_run = DatasetRun(
        user_id=user.id,
        domain="retail",
        load_type="bulk",
        format="json",
        record_count=1,
        status="completed",
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
    )
    db_session.add_all([old_run, new_run])
    db_session.flush()
    db_session.add_all(
        [
            GeneratedFile(
                run_id=old_run.id,
                file_name="customers.json",
                file_path=str(old_file),
                storage_backend="local",
                object_key="old-run/customers.json",
                file_format="json",
                size_bytes=old_file.stat().st_size,
                file_size_mb=0.0,
                content_type="application/json",
            ),
            GeneratedFile(
                run_id=new_run.id,
                file_name="customers.json",
                file_path=str(new_file),
                storage_backend="local",
                object_key="new-run/customers.json",
                file_format="json",
                size_bytes=new_file.stat().st_size,
                file_size_mb=0.0,
                content_type="application/json",
            ),
        ]
    )
    db_session.commit()

    from backend.app.services.storage import LocalStorageService

    result = cleanup_stored_generated_files(
        db_session,
        retention_days=7,
        storage=LocalStorageService(output_dir),
        dry_run=False,
        now=datetime.now(timezone.utc),
    )

    assert result.scanned == 1
    assert result.deleted == 1
    assert result.freed_bytes == 3
    assert not old_file.exists()
    assert new_file.exists()


def test_expired_run_history_cleanup_deletes_files_and_run_rows(db_session, tmp_path):
    output_dir = tmp_path / "backend-output"
    old_file = output_dir / "old-run" / "customers.json"
    old_file.parent.mkdir(parents=True)
    old_file.write_text("old", encoding="utf-8")
    new_file = output_dir / "new-run" / "customers.json"
    new_file.parent.mkdir(parents=True)
    new_file.write_text("new", encoding="utf-8")
    user = User(email="history-retention@example.test", plan="free")
    db_session.add(user)
    db_session.flush()
    old_run = DatasetRun(
        user_id=user.id,
        domain="retail",
        load_type="bulk",
        format="json",
        record_count=1,
        status="completed",
        started_at=datetime.now(timezone.utc) - timedelta(days=10),
        completed_at=datetime.now(timezone.utc) - timedelta(days=10),
    )
    new_run = DatasetRun(
        user_id=user.id,
        domain="banking",
        load_type="bulk",
        format="json",
        record_count=1,
        status="completed",
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
    )
    db_session.add_all([old_run, new_run])
    db_session.flush()
    old_job = GenerationJob(
        run_id=old_run.id,
        status="completed",
        request_payload="{}",
        completed_at=old_run.completed_at,
    )
    db_session.add_all(
        [
            GeneratedFile(
                run_id=old_run.id,
                file_name="customers.json",
                file_path=str(old_file),
                storage_backend="local",
                object_key="old-run/customers.json",
                file_format="json",
                size_bytes=old_file.stat().st_size,
                file_size_mb=0.0,
                content_type="application/json",
            ),
            GeneratedFile(
                run_id=new_run.id,
                file_name="customers.json",
                file_path=str(new_file),
                storage_backend="local",
                object_key="new-run/customers.json",
                file_format="json",
                size_bytes=new_file.stat().st_size,
                file_size_mb=0.0,
                content_type="application/json",
            ),
        ]
    )
    db_session.add(old_job)
    db_session.commit()

    from backend.app.services.storage import LocalStorageService

    result = cleanup_expired_run_history(
        db_session,
        retention_days=7,
        storage=LocalStorageService(output_dir),
        dry_run=False,
        now=datetime.now(timezone.utc),
    )
    db_session.commit()

    assert result.scanned == 1
    assert result.deleted == 1
    assert not old_file.exists()
    assert new_file.exists()
    assert db_session.get(DatasetRun, old_run.id) is None
    assert db_session.get(DatasetRun, new_run.id) is not None
    assert db_session.get(GenerationJob, old_job.id).run_id is None


def test_expired_run_history_cleanup_tolerates_unsafe_legacy_file_metadata(db_session, tmp_path):
    output_dir = tmp_path / "backend-output"
    output_dir.mkdir()
    user = User(email="history-legacy-retention@example.test", plan="free")
    db_session.add(user)
    db_session.flush()
    old_run = DatasetRun(
        user_id=user.id,
        domain="retail",
        load_type="bulk",
        format="json",
        record_count=1,
        status="completed",
        started_at=datetime.now(timezone.utc) - timedelta(days=10),
        completed_at=datetime.now(timezone.utc) - timedelta(days=10),
    )
    db_session.add(old_run)
    db_session.flush()
    db_session.add(
        GeneratedFile(
            run_id=old_run.id,
            file_name="customers.json",
            file_path="customers.json",
            storage_backend="local",
            object_key="",
            file_format="json",
            size_bytes=10,
            file_size_mb=0.0,
            content_type="application/json",
        )
    )
    db_session.commit()

    from backend.app.services.storage import LocalStorageService

    result = cleanup_expired_run_history(
        db_session,
        retention_days=7,
        storage=LocalStorageService(output_dir),
        dry_run=False,
        now=datetime.now(timezone.utc),
    )
    db_session.commit()

    assert result.scanned == 1
    assert result.deleted == 0
    assert db_session.get(DatasetRun, old_run.id) is None


def test_runs_api_removes_history_older_than_retention(tmp_path, monkeypatch):
    output_dir = tmp_path / "backend-output"
    old_file = output_dir / "old-run" / "customers.json"
    old_file.parent.mkdir(parents=True)
    old_file.write_text("old", encoding="utf-8")
    new_file = output_dir / "new-run" / "customers.json"
    new_file.parent.mkdir(parents=True)
    new_file.write_text("new", encoding="utf-8")
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))
    monkeypatch.setenv("GENERATED_FILE_RETENTION_DAYS", "7")
    get_settings.cache_clear()
    engine = create_engine(f"sqlite:///{tmp_path / 'history_retention.db'}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    user = User(email="history-api-retention@example.test", plan="free")
    db.add(user)
    db.flush()
    old_run = DatasetRun(
        user_id=user.id,
        domain="retail",
        load_type="bulk",
        format="json",
        record_count=1,
        status="completed",
        started_at=datetime.now(timezone.utc) - timedelta(days=10),
        completed_at=datetime.now(timezone.utc) - timedelta(days=10),
    )
    new_run = DatasetRun(
        user_id=user.id,
        domain="banking",
        load_type="bulk",
        format="json",
        record_count=1,
        status="completed",
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
    )
    db.add_all([old_run, new_run])
    db.flush()
    db.add_all(
        [
            GeneratedFile(
                run_id=old_run.id,
                file_name="customers.json",
                file_path=str(old_file),
                storage_backend="local",
                object_key="old-run/customers.json",
                file_format="json",
                size_bytes=old_file.stat().st_size,
                file_size_mb=0.0,
                content_type="application/json",
            ),
            GeneratedFile(
                run_id=new_run.id,
                file_name="customers.json",
                file_path=str(new_file),
                storage_backend="local",
                object_key="new-run/customers.json",
                file_format="json",
                size_bytes=new_file.stat().st_size,
                file_size_mb=0.0,
                content_type="application/json",
            ),
        ]
    )
    db.commit()
    db.close()

    def override_get_db():
        session: Session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app = create_app()
    app.state.SessionLocal = TestingSessionLocal
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        response = client.get("/api/v1/runs")

    assert response.status_code == 200
    domains = {item["domain"] for item in response.json()["items"]}
    assert domains == {"banking"}
    assert not old_file.exists()
    assert new_file.exists()

    Base.metadata.drop_all(bind=engine)
    get_settings.cache_clear()


def test_storage_aware_retention_deletes_mocked_s3_generated_files(db_session):
    class MockStorage:
        storage_backend = "s3"

        def __init__(self) -> None:
            self.deleted_keys: list[str] = []

        def delete_generated_file(self, generated_file):
            self.deleted_keys.append(generated_file.object_key)
            return generated_file.size_bytes

    user = User(email="remote-retention@example.test", plan="free")
    db_session.add(user)
    db_session.flush()
    old_run = DatasetRun(
        user_id=user.id,
        domain="retail",
        load_type="bulk",
        format="json",
        record_count=1,
        status="completed",
        started_at=datetime.now(timezone.utc) - timedelta(days=10),
        completed_at=datetime.now(timezone.utc) - timedelta(days=10),
    )
    db_session.add(old_run)
    db_session.flush()
    db_session.add(
        GeneratedFile(
            run_id=old_run.id,
            file_name="customers.json",
            file_path="retention-bucket/old-run/customers.json",
            storage_backend="s3",
            object_key="old-run/customers.json",
            file_format="json",
            size_bytes=123,
            file_size_mb=0.000117,
            content_type="application/json",
        )
    )
    db_session.commit()
    storage = MockStorage()

    result = cleanup_stored_generated_files(
        db_session,
        retention_days=7,
        storage=storage,
        dry_run=False,
        now=datetime.now(timezone.utc),
    )

    assert result.scanned == 1
    assert result.deleted == 1
    assert result.freed_bytes == 123
    assert storage.deleted_keys == ["old-run/customers.json"]
