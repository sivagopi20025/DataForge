from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import ScenarioTemplate


class ScenarioTemplateRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, **values) -> ScenarioTemplate:
        template = ScenarioTemplate(**values)
        self.db.add(template)
        self.db.flush()
        return template

    def get(self, template_id: str) -> ScenarioTemplate | None:
        return self.db.get(ScenarioTemplate, template_id)

    def list(self, *, limit: int = 100, offset: int = 0) -> list[ScenarioTemplate]:
        return list(self.db.scalars(select(ScenarioTemplate).order_by(ScenarioTemplate.updated_at.desc()).limit(limit).offset(offset)))

    def update(self, template: ScenarioTemplate, **values) -> ScenarioTemplate:
        for key, value in values.items():
            if value is not None and hasattr(template, key):
                setattr(template, key, value)
        self.db.flush()
        return template

    def mark_used(self, template: ScenarioTemplate, when: datetime) -> ScenarioTemplate:
        template.last_used_at = when
        self.db.flush()
        return template

    def delete(self, template: ScenarioTemplate) -> None:
        self.db.delete(template)
        self.db.flush()
