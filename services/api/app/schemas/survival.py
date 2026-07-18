from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TokenAccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    account_type: Literal["read", "output"]
    balance_units: int
    initial_balance_units: int
    updated_at: datetime


class TurnUsageSummary(BaseModel):
    turn_id: str
    input_tokens: int
    output_tokens: int
    read_change_units: int
    output_change_units: int
    completed_at: datetime


class SurvivalStatusRead(BaseModel):
    units_per_token: int
    accounts: list[TokenAccountRead]
    latest_turn: TurnUsageSummary | None


class TokenTransactionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    turn_id: str | None
    feedback_event_id: str | None
    account_type: str
    transaction_type: str
    amount_units: int
    balance_before: int
    balance_after: int
    idempotency_key: str
    metadata_value: dict[str, object]
    created_at: datetime


class FeedbackCreate(BaseModel):
    rating: Literal["satisfied", "unsatisfied"]
    comment: str | None = Field(default=None, max_length=2_000)


class QualityFeedbackRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    turn_id: str
    rating: str
    comment: str | None
    created_at: datetime


class SurvivalRewardRead(BaseModel):
    granted_now: bool
    transactions: list[TokenTransactionRead]


class FeedbackResultRead(BaseModel):
    quality_feedback: QualityFeedbackRead
    survival_reward: SurvivalRewardRead


class ExecutionTraceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    turn_id: str
    model_id: str
    memory_revision_ids: list[str]
    skill_revision_ids: list[str]
    tool_names: list[str]
    provider_raw_usage: list[dict[str, object]]
    normalized_usage: dict[str, object]
    input_tokens: int
    output_tokens: int
    latency_ms: int
    completion_status: str
    objective_result: dict[str, object]
    created_at: datetime
