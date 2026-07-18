from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from services.api.app.db.models import MemoryItem, MemoryRevision, MemorySnapshot

FORMAL_MEMORY_CHAR_LIMIT = 18_000
CORE_MEMORY_CHAR_LIMIT = 4_000
RELEVANT_MEMORY_CHAR_LIMIT = 6_000


@dataclass(frozen=True)
class FormalMemoryContext:
    content: str | None
    revision_ids: list[str]
    char_count: int


def formal_char_count(db: Session) -> int:
    return int(
        db.scalar(
            select(func.coalesce(func.sum(MemoryItem.char_count), 0)).where(
                MemoryItem.status == "active"
            )
        )
        or 0
    )


def _take(items: list[MemoryItem], limit: int, seen: set[str]) -> list[MemoryItem]:
    result: list[MemoryItem] = []
    used = 0
    for item in items:
        if item.id in seen or used + item.char_count > limit:
            if not result and item.locked:
                result.append(item)
                seen.add(item.id)
                used = limit
            continue
        result.append(item)
        seen.add(item.id)
        used += item.char_count
    return result


def retrieve_formal_memory(db: Session, *, query: str) -> FormalMemoryContext:
    active = list(
        db.scalars(
            select(MemoryItem)
            .where(MemoryItem.status == "active")
            .order_by(
                MemoryItem.locked.desc(), MemoryItem.priority.desc(), MemoryItem.updated_at.desc()
            )
        )
    )
    seen: set[str] = set()
    core = _take(active, CORE_MEMORY_CHAR_LIMIT, seen)
    relevant: list[MemoryItem] = []
    terms = [term for term in re.findall(r"[\w\u4e00-\u9fff]+", query.lower()) if len(term) > 1][
        :12
    ]
    if terms:
        match = " OR ".join(f'"{term.replace(chr(34), "")}"' for term in terms)
        try:
            with db.begin_nested():
                ids = [
                    row[0]
                    for row in db.execute(
                        text(
                            "SELECT memory_items.id FROM memory_items_fts JOIN memory_items "
                            "ON memory_items_fts.rowid=memory_items.rowid "
                            "WHERE memory_items_fts MATCH :match "
                            "AND memory_items.status='active' "
                            "ORDER BY bm25(memory_items_fts) LIMIT 50"
                        ),
                        {"match": match},
                    )
                ]
            by_id = {item.id: item for item in active}
            relevant = _take(
                [by_id[item_id] for item_id in ids if item_id in by_id],
                RELEVANT_MEMORY_CHAR_LIMIT,
                seen,
            )
        except Exception:
            relevant = _take(
                [
                    item
                    for item in active
                    if any(
                        term in f"{item.title} {item.content} {' '.join(item.tags)}".lower()
                        for term in terms
                    )
                ],
                RELEVANT_MEMORY_CHAR_LIMIT,
                seen,
            )
    chosen = core + relevant
    if not chosen:
        return FormalMemoryContext(None, [], 0)
    remaining = CORE_MEMORY_CHAR_LIMIT + RELEVANT_MEMORY_CHAR_LIMIT
    lines: list[str] = []
    injected_chars = 0
    for item in chosen:
        prefix = f"- [{item.category}] {item.title}: "
        available = max(0, remaining - len(prefix))
        content = item.content[:available]
        lines.append(prefix + content)
        injected_chars += len(content)
        remaining -= len(prefix) + len(content)
        if remaining <= 0:
            break
    body = "Formal long-term memory. Apply only relevant facts and instructions:\n" + "\n".join(
        lines
    )
    return FormalMemoryContext(
        body, [item.current_revision_id for item in chosen[: len(lines)]], injected_chars
    )


def create_revision(
    db: Session,
    item: MemoryItem,
    *,
    operation: str,
    source_turn_ids: list[str],
    created_by: str,
    reason: str | None,
    job_id: str | None = None,
) -> MemoryRevision:
    revision = MemoryRevision(
        id=str(uuid4()),
        memory_item_id=item.id,
        previous_revision_id=item.current_revision_id if item.current_revision_id else None,
        operation=operation,
        title=item.title,
        content=item.content,
        category=item.category,
        tags_json=item.tags_json,
        priority=item.priority,
        status=item.status,
        locked=item.locked,
        source_turn_ids_json=json.dumps(source_turn_ids),
        cognitive_job_id=job_id,
        created_by=created_by,
        reason=reason,
        created_at=datetime.now(UTC),
    )
    db.add(revision)
    db.flush()
    item.current_revision_id = revision.id
    item.char_count = len(item.content)
    return revision


def create_snapshot(db: Session, *, version: int, job_id: str | None) -> MemorySnapshot:
    revisions = list(
        db.scalars(
            select(MemoryItem.current_revision_id)
            .where(MemoryItem.status == "active")
            .order_by(MemoryItem.id)
        )
    )
    snapshot = MemorySnapshot(
        id=str(uuid4()),
        version=version,
        cognitive_job_id=job_id,
        revision_ids_json=json.dumps(revisions),
        formal_char_count=formal_char_count(db),
        created_at=datetime.now(UTC),
    )
    db.add(snapshot)
    return snapshot
