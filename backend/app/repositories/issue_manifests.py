from __future__ import annotations

from sqlalchemy.orm import Session

from backend.app.models import IssueManifest


class IssueManifestRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, *, run_id: str, issue_type: str, issue_count: int, issue_percentage: float) -> IssueManifest:
        manifest = IssueManifest(
            run_id=run_id,
            issue_type=issue_type,
            issue_count=issue_count,
            issue_percentage=issue_percentage,
        )
        self.db.add(manifest)
        self.db.flush()
        return manifest
