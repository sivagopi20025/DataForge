from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.app.models import StreamEvent, StreamSession


class StreamSessionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        domain: str,
        event_types: list[str],
        events_per_second: int,
        duration_minutes: int,
        file_format: str,
        seed: int,
        failure_injections: dict[str, Any],
        stream_token_hash: str,
        stream_token_expires_at: datetime,
        webhook_url: str | None = None,
        webhook_secret_hash: str | None = None,
        started_at: datetime,
        estimated_end_at: datetime,
        status: str = "queued",
    ) -> StreamSession:
        session = StreamSession(
            domain=domain,
            event_types=json.dumps(event_types),
            events_per_second=events_per_second,
            duration_minutes=duration_minutes,
            format=file_format,
            seed=seed,
            failure_injections=json.dumps(failure_injections),
            stream_token_hash=stream_token_hash,
            stream_token_expires_at=stream_token_expires_at,
            webhook_url=webhook_url,
            webhook_secret_hash=webhook_secret_hash,
            webhook_delivery_summary="{}",
            status=status,
            failure_summary="{}",
            started_at=started_at,
            estimated_end_at=estimated_end_at,
        )
        self.db.add(session)
        self.db.flush()
        return session

    def get(self, stream_id: str, *, include_events: bool = False) -> StreamSession | None:
        statement = select(StreamSession).where(StreamSession.id == stream_id)
        if include_events:
            statement = statement.options(selectinload(StreamSession.events))
        return self.db.scalar(statement)

    def mark_running(self, session: StreamSession) -> StreamSession:
        session.status = "running"
        self.db.flush()
        return session

    def mark_completed(self, session: StreamSession, *, completed_at: datetime, failure_summary: dict[str, int]) -> StreamSession:
        session.status = "completed"
        session.completed_at = completed_at
        session.failure_summary = json.dumps(failure_summary)
        self.db.flush()
        return session

    def mark_failed(self, session: StreamSession, *, completed_at: datetime, failure_summary: dict[str, int]) -> StreamSession:
        session.status = "failed"
        session.completed_at = completed_at
        session.failure_summary = json.dumps(failure_summary)
        self.db.flush()
        return session

    def mark_stopped(self, session: StreamSession, *, completed_at: datetime) -> StreamSession:
        session.status = "stopped"
        session.completed_at = completed_at
        self.db.flush()
        return session

    def add_event(
        self,
        *,
        stream_id: str,
        event: dict[str, Any],
        raw_event: str | None = None,
        is_malformed: bool = False,
    ) -> StreamEvent:
        row = StreamEvent(
            stream_id=stream_id,
            event_id=event["event_id"],
            event_type=event["event_type"],
            domain=event["domain"],
            sequence_number=event["sequence_number"],
            correlation_id=event["correlation_id"],
            event_time=event["event_time"],
            ingestion_time=event["ingestion_time"],
            payload=json.dumps(event["payload"], default=str),
            injected_issues=json.dumps(event["injected_issues"]),
            raw_event=raw_event,
            is_malformed=is_malformed,
        )
        self.db.add(row)
        self.db.flush()
        return row

    def list_events(self, stream_id: str, *, limit: int = 100, offset: int = 0) -> list[StreamEvent]:
        return self.find_events(stream_id, limit=limit, offset=offset)

    def find_events(
        self,
        stream_id: str,
        *,
        limit: int = 100,
        offset: int = 0,
        after_sequence: int | None = None,
        event_type: str | None = None,
    ) -> list[StreamEvent]:
        statement = select(StreamEvent).where(StreamEvent.stream_id == stream_id)
        if after_sequence is not None:
            statement = statement.where(StreamEvent.sequence_number > after_sequence)
        if event_type is not None:
            statement = statement.where(StreamEvent.event_type == event_type)
        return list(
            self.db.scalars(
                statement
                .order_by(StreamEvent.sequence_number.asc(), StreamEvent.created_at.asc())
                .limit(limit)
                .offset(offset)
            )
        )

    def latest_event(self, stream_id: str, *, event_type: str | None = None) -> StreamEvent | None:
        statement = select(StreamEvent).where(StreamEvent.stream_id == stream_id)
        if event_type is not None:
            statement = statement.where(StreamEvent.event_type == event_type)
        return self.db.scalar(statement.order_by(StreamEvent.sequence_number.desc(), StreamEvent.created_at.desc()).limit(1))

    def count_events(self, stream_id: str, *, after_sequence: int | None = None, event_type: str | None = None) -> int:
        from sqlalchemy import func

        statement = select(func.count(StreamEvent.id)).where(StreamEvent.stream_id == stream_id)
        if after_sequence is not None:
            statement = statement.where(StreamEvent.sequence_number > after_sequence)
        if event_type is not None:
            statement = statement.where(StreamEvent.event_type == event_type)
        return int(self.db.scalar(statement) or 0)

    def update_counts(self, session: StreamSession, *, generated: int, failed: int) -> StreamSession:
        session.events_generated = generated
        session.events_failed = failed
        self.db.flush()
        return session

    def update_webhook_summary(self, session: StreamSession, summary: dict[str, Any]) -> StreamSession:
        session.webhook_delivery_summary = json.dumps(summary)
        self.db.flush()
        return session
