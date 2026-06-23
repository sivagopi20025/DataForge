from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.models import AdminMetric


class AdminMetricsRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, *, metric_name: str, metric_value: float, metric_date: date) -> AdminMetric:
        metric = AdminMetric(metric_name=metric_name, metric_value=metric_value, metric_date=metric_date)
        self.db.add(metric)
        self.db.flush()
        return metric

    def sum_metric(self, metric_name: str) -> float:
        return float(
            self.db.scalar(
                select(func.coalesce(func.sum(AdminMetric.metric_value), 0)).where(AdminMetric.metric_name == metric_name)
            )
            or 0
        )
