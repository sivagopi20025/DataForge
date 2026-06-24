from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.models import GeneratedFile

if TYPE_CHECKING:
    from backend.app.services.storage import StoredObject


class GeneratedFileRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, *, run_id: str, path: Path, file_format: str, stored_object: StoredObject | None = None) -> GeneratedFile:
        size_bytes = path.stat().st_size if path.exists() else 0
        generated = GeneratedFile(
            run_id=run_id,
            file_name=path.name,
            file_path=stored_object.file_path if stored_object else str(path),
            storage_backend=stored_object.storage_backend if stored_object else "local",
            object_key=stored_object.object_key if stored_object else str(path),
            file_format=file_format,
            size_bytes=stored_object.size_bytes if stored_object else size_bytes,
            file_size_mb=round((stored_object.size_bytes if stored_object else size_bytes) / (1024 * 1024), 6),
            content_type=stored_object.content_type if stored_object else "application/octet-stream",
        )
        self.db.add(generated)
        self.db.flush()
        return generated

    def get_for_run(self, *, run_id: str, file_id: str) -> GeneratedFile | None:
        return self.db.scalar(
            select(GeneratedFile).where(
                GeneratedFile.id == file_id,
                GeneratedFile.run_id == run_id,
            )
        )

    def count(self) -> int:
        return int(self.db.scalar(select(func.count(GeneratedFile.id))) or 0)
