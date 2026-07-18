from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from services.api.app.db.base import Base


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    messages: Mapped[list[Message]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan", order_by="Message.sequence"
    )
    turns: Mapped[list[Turn]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )
    tool_executions: Mapped[list[ToolExecution]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="ToolExecution.call_sequence",
    )

    @property
    def feedback_events(self) -> list[FeedbackEvent]:
        return sorted(
            (event for turn in self.turns for event in turn.feedback_events),
            key=lambda event: event.created_at,
        )


class Turn(Base):
    __tablename__ = "turns"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    user_message_id: Mapped[str] = mapped_column(String(36), nullable=False)
    source_turn_id: Mapped[str | None] = mapped_column(
        ForeignKey("turns.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    error_message: Mapped[str | None] = mapped_column(Text(), nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    conversation: Mapped[Conversation] = relationship(back_populates="turns")
    messages: Mapped[list[Message]] = relationship(back_populates="turn")
    tool_executions: Mapped[list[ToolExecution]] = relationship(
        back_populates="turn", cascade="all, delete-orphan", order_by="ToolExecution.call_sequence"
    )
    execution_trace: Mapped[TurnExecutionTrace | None] = relationship(
        back_populates="turn", cascade="all, delete-orphan", uselist=False
    )
    feedback_events: Mapped[list[FeedbackEvent]] = relationship(
        back_populates="turn", cascade="all, delete-orphan", order_by="FeedbackEvent.created_at"
    )
    token_transactions: Mapped[list[TokenTransaction]] = relationship(back_populates="turn")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    turn_id: Mapped[str | None] = mapped_column(
        ForeignKey("turns.id", ondelete="SET NULL"), index=True, nullable=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text(), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    conversation: Mapped[Conversation] = relationship(back_populates="messages")
    turn: Mapped[Turn | None] = relationship(back_populates="messages")


class ModelSetting(Base):
    __tablename__ = "model_settings"

    role: Mapped[str] = mapped_column(String(32), primary_key=True)
    base_url: Mapped[str] = mapped_column(String(500), nullable=False)
    model: Mapped[str] = mapped_column(String(200), nullable=False)
    timeout_seconds: Mapped[int] = mapped_column(Integer(), nullable=False, default=120)
    max_output_tokens: Mapped[int] = mapped_column(Integer(), nullable=False, default=8192)
    temperature: Mapped[float | None] = mapped_column(Float(), nullable=True)
    api_key_env: Mapped[str] = mapped_column(
        String(100), nullable=False, default="OPENAI_API_KEY"
    )
    enabled: Mapped[bool] = mapped_column(Boolean(), nullable=False, default=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ToolExecution(Base):
    __tablename__ = "tool_executions"
    __table_args__ = (
        UniqueConstraint("turn_id", "provider_call_id", name="uq_tool_execution_turn_call"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    turn_id: Mapped[str] = mapped_column(
        ForeignKey("turns.id", ondelete="CASCADE"), index=True
    )
    provider_call_id: Mapped[str] = mapped_column(String(200), nullable=False)
    call_sequence: Mapped[int] = mapped_column(Integer(), nullable=False)
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False)
    arguments_json: Mapped[str] = mapped_column(Text(), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    result_json: Mapped[str | None] = mapped_column(Text(), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    conversation: Mapped[Conversation] = relationship(back_populates="tool_executions")
    turn: Mapped[Turn] = relationship(back_populates="tool_executions")

    @property
    def arguments(self) -> dict[str, object]:
        value = json.loads(self.arguments_json)
        return value if isinstance(value, dict) else {}

    @property
    def result(self) -> dict[str, object] | None:
        if self.result_json is None:
            return None
        value = json.loads(self.result_json)
        return value if isinstance(value, dict) else None


class TokenAccount(Base):
    __tablename__ = "token_accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_type: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    balance_units: Mapped[int] = mapped_column(BigInteger(), nullable=False)
    initial_balance_units: Mapped[int] = mapped_column(BigInteger(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class FeedbackEvent(Base):
    __tablename__ = "feedback_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    turn_id: Mapped[str] = mapped_column(
        ForeignKey("turns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rating: Mapped[str] = mapped_column(String(20), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    turn: Mapped[Turn] = relationship(back_populates="feedback_events")
    token_transactions: Mapped[list[TokenTransaction]] = relationship(
        back_populates="feedback_event"
    )


class TokenTransaction(Base):
    __tablename__ = "token_transactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    turn_id: Mapped[str | None] = mapped_column(
        ForeignKey("turns.id", ondelete="SET NULL"), nullable=True, index=True
    )
    feedback_event_id: Mapped[str | None] = mapped_column(
        ForeignKey("feedback_events.id", ondelete="SET NULL"), nullable=True, index=True
    )
    account_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    transaction_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    amount_units: Mapped[int] = mapped_column(BigInteger(), nullable=False)
    balance_before: Mapped[int] = mapped_column(BigInteger(), nullable=False)
    balance_after: Mapped[int] = mapped_column(BigInteger(), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(250), nullable=False, unique=True)
    metadata_json: Mapped[str] = mapped_column(Text(), nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    turn: Mapped[Turn | None] = relationship(back_populates="token_transactions")
    feedback_event: Mapped[FeedbackEvent | None] = relationship(
        back_populates="token_transactions"
    )

    @property
    def metadata_value(self) -> dict[str, object]:
        value = json.loads(self.metadata_json)
        return value if isinstance(value, dict) else {}


class TurnExecutionTrace(Base):
    __tablename__ = "turn_execution_traces"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    turn_id: Mapped[str] = mapped_column(
        ForeignKey("turns.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    model_id: Mapped[str] = mapped_column(String(200), nullable=False)
    memory_revision_ids_json: Mapped[str] = mapped_column(Text(), nullable=False, default="[]")
    skill_revision_ids_json: Mapped[str] = mapped_column(Text(), nullable=False, default="[]")
    tool_names_json: Mapped[str] = mapped_column(Text(), nullable=False, default="[]")
    provider_raw_usage_json: Mapped[str] = mapped_column(Text(), nullable=False)
    normalized_usage_json: Mapped[str] = mapped_column(Text(), nullable=False)
    input_tokens: Mapped[int] = mapped_column(BigInteger(), nullable=False)
    output_tokens: Mapped[int] = mapped_column(BigInteger(), nullable=False)
    latency_ms: Mapped[int] = mapped_column(BigInteger(), nullable=False)
    completion_status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    objective_result_json: Mapped[str] = mapped_column(Text(), nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    turn: Mapped[Turn] = relationship(back_populates="execution_trace")

    @staticmethod
    def _json_value(raw: str, fallback: object) -> object:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return fallback

    @property
    def memory_revision_ids(self) -> list[str]:
        value = self._json_value(self.memory_revision_ids_json, [])
        return value if isinstance(value, list) else []

    @property
    def skill_revision_ids(self) -> list[str]:
        value = self._json_value(self.skill_revision_ids_json, [])
        return value if isinstance(value, list) else []

    @property
    def tool_names(self) -> list[str]:
        value = self._json_value(self.tool_names_json, [])
        return value if isinstance(value, list) else []

    @property
    def provider_raw_usage(self) -> list[dict[str, object]]:
        value = self._json_value(self.provider_raw_usage_json, [])
        return value if isinstance(value, list) else []

    @property
    def normalized_usage(self) -> dict[str, object]:
        value = self._json_value(self.normalized_usage_json, {})
        return value if isinstance(value, dict) else {}

    @property
    def objective_result(self) -> dict[str, object]:
        value = self._json_value(self.objective_result_json, {})
        return value if isinstance(value, dict) else {}
