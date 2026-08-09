from __future__ import annotations

import argparse
import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload

from backend.app.core.config import get_settings
from backend.app.db.session import SessionLocal
from backend.app.models import DatasetRun, GenerationJob
from backend.app.services.storage import StorageService, get_storage_service


@dataclass(frozen=True)
class CleanupResult:
    scanned: int
    deleted: int
    freed_bytes: int


def cleanup_generated_files(output_dir: Path, retention_days: int, *, dry_run: bool = True, now: datetime | None = None) -> CleanupResult:
    """Delete expired generated run directories from a local output directory.

    A run directory is considered expired when its latest mtime is older than
    `retention_days`. This is intentionally filesystem-only; database row
    retention should be handled by a future migration/job once user-facing
    retention semantics are finalized.
    """

    if retention_days < 1:
        raise ValueError("retention_days must be at least 1")
    if not output_dir.exists():
        return CleanupResult(scanned=0, deleted=0, freed_bytes=0)

    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=retention_days)
    scanned = 0
    deleted = 0
    freed_bytes = 0

    for run_dir in sorted(path for path in output_dir.iterdir() if path.is_dir()):
        scanned += 1
        latest_mtime = max((path.stat().st_mtime for path in run_dir.rglob("*") if path.exists()), default=run_dir.stat().st_mtime)
        latest_modified = datetime.fromtimestamp(latest_mtime, tz=timezone.utc)
        if latest_modified >= cutoff:
            continue
        size = sum(path.stat().st_size for path in run_dir.rglob("*") if path.is_file())
        if not dry_run:
            shutil.rmtree(run_dir)
        deleted += 1
        freed_bytes += size

    return CleanupResult(scanned=scanned, deleted=deleted, freed_bytes=freed_bytes)


def cleanup_stored_generated_files(
    db: Session,
    retention_days: int,
    *,
    storage: StorageService | None = None,
    dry_run: bool = True,
    now: datetime | None = None,
    delete_run_records: bool = False,
) -> CleanupResult:
    """Delete expired generated objects through the configured storage backend.

    By default this leaves database rows in place for audit/history. When
    `delete_run_records` is true, expired dataset runs are deleted after their
    generated objects are removed, which also removes related generated file,
    issue, and validation rows through ORM cascades.
    """

    if retention_days < 1:
        raise ValueError("retention_days must be at least 1")
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=retention_days)
    active_storage = storage or get_storage_service()
    runs = db.scalars(
        select(DatasetRun)
        .where(DatasetRun.completed_at.is_not(None), DatasetRun.completed_at < cutoff)
        .options(selectinload(DatasetRun.generated_files))
    ).all()

    scanned = 0
    deleted = 0
    freed_bytes = 0
    for run in runs:
        for generated_file in run.generated_files:
            scanned += 1
            if dry_run:
                deleted += 1
                freed_bytes += int(generated_file.size_bytes or 0)
                continue
            try:
                deleted_bytes = active_storage.delete_generated_file(generated_file)
            except ValueError:
                deleted_bytes = 0
            if deleted_bytes:
                deleted += 1
                freed_bytes += deleted_bytes
        if delete_run_records and not dry_run:
            db.execute(update(GenerationJob).where(GenerationJob.run_id == run.id).values(run_id=None))
            db.delete(run)

    if delete_run_records and not dry_run:
        db.flush()

    return CleanupResult(scanned=scanned, deleted=deleted, freed_bytes=freed_bytes)


def cleanup_expired_run_history(
    db: Session,
    retention_days: int,
    *,
    storage: StorageService | None = None,
    dry_run: bool = True,
    now: datetime | None = None,
) -> CleanupResult:
    """Delete expired generated files and their run history rows."""

    return cleanup_stored_generated_files(
        db,
        retention_days,
        storage=storage,
        dry_run=dry_run,
        now=now,
        delete_run_records=True,
    )


def main(argv: list[str] | None = None) -> int:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Clean up expired DataForge generated files")
    parser.add_argument("--output-dir", type=Path, default=settings.output_dir)
    parser.add_argument("--retention-days", type=int, default=settings.generated_file_retention_days)
    parser.add_argument("--apply", action="store_true", help="delete files; omit for dry-run")
    parser.add_argument("--storage-aware", action="store_true", help="delete generated files through configured storage backend")
    args = parser.parse_args(argv)
    if args.storage_aware:
        db = SessionLocal()
        try:
            result = cleanup_stored_generated_files(db, args.retention_days, dry_run=not args.apply)
        finally:
            db.close()
    else:
        result = cleanup_generated_files(args.output_dir, args.retention_days, dry_run=not args.apply)
    mode = "deleted" if args.apply else "would delete"
    print(f"Scanned {result.scanned}; {mode} {result.deleted}; freed_bytes={result.freed_bytes}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
