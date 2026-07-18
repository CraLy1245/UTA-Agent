from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from services.api.app.db.models import MemoryDelta

REALTIME_DELTA_CHAR_LIMIT = 2_000
ACTIVE_STATUSES = ("pending", "deferred_capacity")

_CORRECTION_PATTERNS = (
    re.compile(r"不是[\s\S]+而是"),
    re.compile(r"这个信息错了"),
    re.compile(r"改成"),
)
_EXPLICIT_PHRASES = (
    "请记住",
    "以后不要",
    "以后都按照",
    "我的偏好是",
    "我不喜欢",
    "我喜欢",
    "以后",
)
_META_QUESTION = re.compile(
    r"(?:我此前|我之前|之前我|已经保存|先前).*(?:什么|哪(?:个|种)?|是否).*[？?]"
)


@dataclass(frozen=True)
class MemoryContext:
    content: str | None
    revision_ids: list[str]
    char_count: int


def _normalized(content: str) -> str:
    return " ".join(content.split())


def explicit_instruction_priority(content: str) -> int | None:
    if _META_QUESTION.search(content):
        return None
    if any(pattern.search(content) for pattern in _CORRECTION_PATTERNS):
        return 100
    if "以后不要" in content:
        return 98
    if "请记住" in content or "以后都按照" in content:
        return 96
    if any(phrase in content for phrase in _EXPLICIT_PHRASES):
        return 90
    return None


def capture_explicit_instruction(
    db: Session, *, source_turn_id: str, user_text: str
) -> MemoryDelta | None:
    priority = explicit_instruction_priority(user_text)
    if priority is None:
        return None
    raw_content = user_text.strip()
    normalized_content = _normalized(raw_content)
    duplicate = db.scalar(
        select(MemoryDelta)
        .where(
            MemoryDelta.normalized_content == normalized_content,
            MemoryDelta.status.in_(ACTIVE_STATUSES),
        )
        .order_by(MemoryDelta.created_at.desc(), MemoryDelta.id.desc())
        .limit(1)
    )
    status = "duplicate_merged" if duplicate is not None else "pending"
    delta = MemoryDelta(
        id=str(uuid4()),
        revision_id=str(uuid4()),
        source_turn_id=source_turn_id,
        raw_content=raw_content,
        normalized_content=normalized_content,
        delta_type="explicit_instruction",
        priority=priority,
        status=status,
        char_count=len(raw_content),
        created_at=datetime.now(UTC),
    )
    db.add(delta)
    db.flush()
    if duplicate is None:
        _rebalance_active_delta(db)
    return delta


def _rebalance_active_delta(db: Session) -> None:
    candidates = list(
        db.scalars(
            select(MemoryDelta).where(MemoryDelta.status.in_(ACTIVE_STATUSES))
        )
    )
    candidates.sort(
        key=lambda delta: (
            -delta.priority,
            -delta.created_at.timestamp(),
            delta.id,
        )
    )
    used = 0
    for delta in candidates:
        if used + delta.char_count <= REALTIME_DELTA_CHAR_LIMIT:
            delta.status = "pending"
            used += delta.char_count
        else:
            delta.status = "deferred_capacity"


def build_memory_context(
    db: Session,
    *,
    excluded_source_turn_ids: set[str],
    available_before: datetime,
) -> MemoryContext:
    query = select(MemoryDelta).where(
        MemoryDelta.status.in_(ACTIVE_STATUSES),
        MemoryDelta.created_at < available_before,
    )
    if excluded_source_turn_ids:
        query = query.where(MemoryDelta.source_turn_id.not_in(excluded_source_turn_ids))
    candidates = list(db.scalars(query))
    candidates.sort(
        key=lambda delta: (
            -delta.priority,
            -delta.created_at.timestamp(),
            delta.id,
        )
    )
    deltas: list[MemoryDelta] = []
    used = 0
    for delta in candidates:
        if used + delta.char_count <= REALTIME_DELTA_CHAR_LIMIT:
            deltas.append(delta)
            used += delta.char_count
    deltas.sort(key=lambda delta: (delta.created_at, delta.id))
    if not deltas:
        return MemoryContext(content=None, revision_ids=[], char_count=0)
    content = (
        "Current real-time memory instructions. These were explicitly provided by the user in "
        "earlier turns and must be followed when relevant:\n"
        + "\n".join(f"- {delta.raw_content}" for delta in deltas)
    )
    return MemoryContext(
        content=content,
        revision_ids=[delta.revision_id for delta in deltas],
        char_count=sum(delta.char_count for delta in deltas),
    )
