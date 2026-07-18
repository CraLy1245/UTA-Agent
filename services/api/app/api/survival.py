from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from services.api.app.db.models import (
    TokenAccount,
    TokenTransaction,
    Turn,
    TurnExecutionTrace,
)
from services.api.app.db.session import get_db
from services.api.app.schemas.survival import (
    ExecutionTraceRead,
    FeedbackCreate,
    FeedbackResultRead,
    QualityFeedbackRead,
    SurvivalRewardRead,
    SurvivalStatusRead,
    TokenAccountRead,
    TokenTransactionRead,
    TurnUsageSummary,
)
from services.survival.ledger import UNITS_PER_TOKEN
from services.survival.quality_feedback import record_quality_feedback
from services.survival.reward import grant_survival_reward, reward_was_granted

router = APIRouter(prefix="/survival", tags=["survival"])
turn_router = APIRouter(prefix="/turns", tags=["survival"])
SessionDep = Annotated[Session, Depends(get_db)]


@router.get("/status", response_model=SurvivalStatusRead)
def get_survival_status(
    db: SessionDep, conversation_id: str | None = None
) -> SurvivalStatusRead:
    accounts = list(db.scalars(select(TokenAccount).order_by(TokenAccount.account_type)))
    if len(accounts) != 2:
        raise HTTPException(status_code=503, detail="Token accounts are not initialized")
    trace_query = select(TurnExecutionTrace).join(Turn)
    if conversation_id:
        trace_query = trace_query.where(Turn.conversation_id == conversation_id)
    latest_trace = db.scalar(
        trace_query.order_by(TurnExecutionTrace.created_at.desc()).limit(1)
    )
    latest_summary = None
    latest_turn = db.get(Turn, latest_trace.turn_id) if latest_trace else None
    if latest_trace and latest_turn and latest_turn.completed_at:
        latest_summary = TurnUsageSummary(
            turn_id=latest_turn.id,
            input_tokens=latest_trace.input_tokens,
            output_tokens=latest_trace.output_tokens,
            read_change_units=-(latest_trace.input_tokens * UNITS_PER_TOKEN),
            output_change_units=-(latest_trace.output_tokens * UNITS_PER_TOKEN),
            completed_at=latest_turn.completed_at,
        )
    return SurvivalStatusRead(
        units_per_token=UNITS_PER_TOKEN,
        accounts=[TokenAccountRead.model_validate(account) for account in accounts],
        latest_turn=latest_summary,
    )


@router.get("/transactions", response_model=list[TokenTransactionRead])
def list_transactions(
    db: SessionDep,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[TokenTransaction]:
    return list(
        db.scalars(
            select(TokenTransaction)
            .order_by(TokenTransaction.created_at.desc(), TokenTransaction.id.desc())
            .limit(limit)
            .offset(offset)
        )
    )


@turn_router.post("/{turn_id}/feedback", response_model=FeedbackResultRead)
def create_feedback(
    turn_id: str, payload: FeedbackCreate, db: SessionDep
) -> FeedbackResultRead:
    db.connection().exec_driver_sql("BEGIN IMMEDIATE")
    turn = db.get(Turn, turn_id)
    if turn is None:
        raise HTTPException(status_code=404, detail="Turn not found")
    if turn.status != "completed":
        raise HTTPException(status_code=409, detail="Only completed turns can be rated")
    trace = db.scalar(
        select(TurnExecutionTrace).where(TurnExecutionTrace.turn_id == turn_id)
    )
    if trace is None:
        raise HTTPException(status_code=409, detail="Turn execution trace is missing")

    feedback = record_quality_feedback(
        db, turn=turn, rating=payload.rating, comment=payload.comment
    )
    reward_entries = (
        grant_survival_reward(db, feedback_event=feedback, trace=trace)
        if payload.rating == "satisfied"
        else []
    )
    db.commit()
    db.refresh(feedback)
    return FeedbackResultRead(
        quality_feedback=QualityFeedbackRead.model_validate(feedback),
        survival_reward=SurvivalRewardRead(
            granted_now=reward_was_granted(reward_entries),
            transactions=[
                TokenTransactionRead.model_validate(entry.transaction)
                for entry in reward_entries
            ],
        ),
    )


@turn_router.get("/{turn_id}/execution-trace", response_model=ExecutionTraceRead)
def get_execution_trace(turn_id: str, db: SessionDep) -> TurnExecutionTrace:
    trace = db.scalar(
        select(TurnExecutionTrace).where(TurnExecutionTrace.turn_id == turn_id)
    )
    if trace is None:
        raise HTTPException(status_code=404, detail="Execution trace not found")
    return trace
