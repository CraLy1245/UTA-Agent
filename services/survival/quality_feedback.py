from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from services.api.app.db.models import FeedbackEvent, Turn


def record_quality_feedback(
    db: Session, *, turn: Turn, rating: str, comment: str | None
) -> FeedbackEvent:
    event = FeedbackEvent(
        id=str(uuid4()),
        turn_id=turn.id,
        rating=rating,
        comment=comment.strip() if comment and comment.strip() else None,
        created_at=datetime.now(UTC),
    )
    db.add(event)
    db.flush()
    return event
