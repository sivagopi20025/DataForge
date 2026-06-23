from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from backend.app.repositories import AdminMetricsRepository


class AnalyticsAggregator:
    """Append-only request-level analytics hook."""

    def __init__(self, db: Session) -> None:
        self.metrics = AdminMetricsRepository(db)
        self.db = db

    def record_api_request(self) -> None:
        self.metrics.create(metric_name="api_requests", metric_value=1, metric_date=date.today())
        self.db.commit()

    def record_download(self) -> None:
        self.metrics.create(metric_name="downloads", metric_value=1, metric_date=date.today())
        self.db.commit()
