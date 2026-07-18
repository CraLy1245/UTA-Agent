from datetime import UTC, datetime
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from services.agent.runtime import cancellation_registry
from services.api.app.db.models import Conversation, Message, Turn
from services.api.app.db.session import get_db
from services.api.app.schemas.conversations import (
    ConversationCreate,
    ConversationDetail,
    ConversationSummary,
    ConversationUpdate,
    TurnCreate,
    TurnRead,
)

router = APIRouter(prefix="/conversations", tags=["conversations"])
turn_router = APIRouter(prefix="/turns", tags=["turns"])
SessionDep = Annotated[Session, Depends(get_db)]


def _get_conversation(db: Session, conversation_id: str) -> Conversation:
    conversation = db.get(Conversation, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


def _next_sequence(db: Session, conversation_id: str) -> int:
    current = db.scalar(
        select(func.max(Message.sequence)).where(Message.conversation_id == conversation_id)
    )
    return int(current or 0) + 1


@router.get("", response_model=list[ConversationSummary])
def list_conversations(db: SessionDep) -> list[Conversation]:
    return list(db.scalars(select(Conversation).order_by(Conversation.updated_at.desc())))


@router.post("", response_model=ConversationSummary, status_code=status.HTTP_201_CREATED)
def create_conversation(
    payload: ConversationCreate, db: SessionDep
) -> Conversation:
    conversation = Conversation(id=str(uuid4()), title=payload.title.strip())
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


@router.get("/{conversation_id}", response_model=ConversationDetail)
def get_conversation(conversation_id: str, db: SessionDep) -> Conversation:
    conversation = db.scalar(
        select(Conversation)
        .where(Conversation.id == conversation_id)
        .options(selectinload(Conversation.messages))
    )
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@router.patch("/{conversation_id}", response_model=ConversationSummary)
def update_conversation(
    conversation_id: str, payload: ConversationUpdate, db: SessionDep
) -> Conversation:
    conversation = _get_conversation(db, conversation_id)
    conversation.title = payload.title.strip()
    db.commit()
    db.refresh(conversation)
    return conversation


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(conversation_id: str, db: SessionDep) -> Response:
    conversation = _get_conversation(db, conversation_id)
    db.delete(conversation)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{conversation_id}/turns", response_model=TurnRead, status_code=201)
def create_turn(
    conversation_id: str, payload: TurnCreate, db: SessionDep
) -> Turn:
    conversation = _get_conversation(db, conversation_id)
    content = payload.content.strip()
    message_id = str(uuid4())
    turn = Turn(
        id=str(uuid4()),
        conversation_id=conversation_id,
        user_message_id=message_id,
        status="pending",
    )
    message = Message(
        id=message_id,
        conversation_id=conversation_id,
        turn_id=turn.id,
        role="user",
        content=content,
        sequence=_next_sequence(db, conversation_id),
    )
    conversation.title = content[:60] if conversation.title == "新对话" else conversation.title
    conversation.updated_at = datetime.now(UTC)
    db.add_all([turn, message])
    db.commit()
    db.refresh(turn)
    return turn


@turn_router.get("/{turn_id}", response_model=TurnRead)
def get_turn(turn_id: str, db: SessionDep) -> Turn:
    turn = db.get(Turn, turn_id)
    if turn is None:
        raise HTTPException(status_code=404, detail="Turn not found")
    return turn


@turn_router.post("/{turn_id}/cancel", response_model=TurnRead)
async def cancel_turn(turn_id: str, db: SessionDep) -> Turn:
    turn = db.get(Turn, turn_id)
    if turn is None:
        raise HTTPException(status_code=404, detail="Turn not found")
    if turn.status in {"pending", "running"}:
        was_running = await cancellation_registry.cancel(turn_id)
        if not was_running and turn.status == "pending":
            turn.status = "cancelled"
            db.commit()
            db.refresh(turn)
    return turn


@turn_router.post("/{turn_id}/regenerate", response_model=TurnRead, status_code=201)
def regenerate_turn(turn_id: str, db: SessionDep) -> Turn:
    source = db.get(Turn, turn_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Turn not found")
    regenerated = Turn(
        id=str(uuid4()),
        conversation_id=source.conversation_id,
        user_message_id=source.user_message_id,
        source_turn_id=source.id,
        status="pending",
    )
    db.add(regenerated)
    db.commit()
    db.refresh(regenerated)
    return regenerated
