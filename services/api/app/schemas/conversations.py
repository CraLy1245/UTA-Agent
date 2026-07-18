from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ConversationCreate(BaseModel):
    title: str = Field(default="新对话", min_length=1, max_length=200)


class ConversationUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    turn_id: str | None
    role: str
    content: str
    sequence: int
    created_at: datetime


class ConversationSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    created_at: datetime
    updated_at: datetime


class ToolExecutionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    turn_id: str
    provider_call_id: str
    call_sequence: int
    tool_name: str
    arguments: dict[str, object]
    status: str
    result: dict[str, object] | None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class FeedbackEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    turn_id: str
    rating: str
    comment: str | None
    created_at: datetime


class ConversationDetail(ConversationSummary):
    messages: list[MessageRead]
    tool_executions: list[ToolExecutionRead]
    feedback_events: list[FeedbackEventRead]


class TurnCreate(BaseModel):
    content: str = Field(min_length=1, max_length=40_000)


class TurnRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    conversation_id: str
    user_message_id: str
    source_turn_id: str | None
    status: str
    error_message: str | None
    input_tokens: int | None
    output_tokens: int | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
