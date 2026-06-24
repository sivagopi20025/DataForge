from __future__ import annotations

from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.models import GeneratedFile


class GeneratedFileRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, *, run_id: str, path: Path, file_format: str) -> GeneratedFile:
        generated = GeneratedFile(
            run_id=run_id,
            file_name=path.name,
            file_path=str(path),
            file_format=file_format,
            file_size_mb=round(path.stat().st_size / (1024 * 1024), 6) if path.exists() else 0.0,
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
