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
    completed_number: Mapped[int | None] = mapped_column(Integer(), nullable=True, unique=True)
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
    api_key_env: Mapped[str] = mapped_column(String(100), nullable=False, default="OPENAI_API_KEY")
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
    turn_id: Mapped[str] = mapped_column(ForeignKey("turns.id", ondelete="CASCADE"), index=True)
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
    feedback_event: Mapped[FeedbackEvent | None] = relationship(back_populates="token_transactions")

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


class MemoryDelta(Base):
    __tablename__ = "memory_delta"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    revision_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    source_turn_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    raw_content: Mapped[str] = mapped_column(Text(), nullable=False)
    normalized_content: Mapped[str] = mapped_column(Text(), nullable=False, index=True)
    delta_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="explicit_instruction"
    )
    priority: Mapped[int] = mapped_column(Integer(), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    char_count: Mapped[int] = mapped_column(Integer(), nullable=False)
    consumed_by_job_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CognitiveState(Base):
    __tablename__ = "cognitive_state"

    id: Mapped[str] = mapped_column(String(20), primary_key=True, default="global")
    completed_turn_count: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    last_consolidated_turn: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    memory_version: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class MemoryItem(Base):
    __tablename__ = "memory_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text(), nullable=False)
    tags_json: Mapped[str] = mapped_column(Text(), nullable=False, default="[]")
    priority: Mapped[int] = mapped_column(Integer(), nullable=False, default=50)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active", index=True)
    locked: Mapped[bool] = mapped_column(Boolean(), nullable=False, default=False)
    current_revision_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    char_count: Mapped[int] = mapped_column(Integer(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    @property
    def tags(self) -> list[str]:
        value = json.loads(self.tags_json)
        return value if isinstance(value, list) else []


class MemoryRevision(Base):
    __tablename__ = "memory_revisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    memory_item_id: Mapped[str] = mapped_column(
        ForeignKey("memory_items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    previous_revision_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    operation: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text(), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    tags_json: Mapped[str] = mapped_column(Text(), nullable=False, default="[]")
    priority: Mapped[int] = mapped_column(Integer(), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    locked: Mapped[bool] = mapped_column(Boolean(), nullable=False)
    source_turn_ids_json: Mapped[str] = mapped_column(Text(), nullable=False, default="[]")
    cognitive_job_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    created_by: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    @property
    def source_turn_ids(self) -> list[str]:
        value = json.loads(self.source_turn_ids_json)
        return value if isinstance(value, list) else []


class MemorySnapshot(Base):
    __tablename__ = "memory_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    version: Mapped[int] = mapped_column(Integer(), nullable=False, unique=True)
    cognitive_job_id: Mapped[str | None] = mapped_column(String(36), nullable=True, unique=True)
    revision_ids_json: Mapped[str] = mapped_column(Text(), nullable=False)
    formal_char_count: Mapped[int] = mapped_column(Integer(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CognitiveJob(Base):
    __tablename__ = "cognitive_jobs"
    __table_args__ = (
        UniqueConstraint(
            "job_type", "start_turn_number", "end_turn_number", name="uq_cognitive_job_range"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    job_type: Mapped[str] = mapped_column(
        String(40), nullable=False, default="memory_consolidation"
    )
    start_turn_number: Mapped[int] = mapped_column(Integer(), nullable=False)
    end_turn_number: Mapped[int] = mapped_column(Integer(), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    memory_version_before: Mapped[int] = mapped_column(Integer(), nullable=False)
    memory_version_after: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text(), nullable=True)
    result_json: Mapped[str | None] = mapped_column(Text(), nullable=True)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Skill(Base):
    __tablename__ = "skills"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(Text(), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active", index=True)
    locked: Mapped[bool] = mapped_column(Boolean(), nullable=False, default=False)
    use_count: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    success_count: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    failure_count: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    selection_weight: Mapped[float] = mapped_column(Float(), nullable=False, default=1.0)
    confidence_score: Mapped[float] = mapped_column(Float(), nullable=False, default=0.5)
    exploration_rate: Mapped[float] = mapped_column(Float(), nullable=False, default=0.1)
    stable_revision_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    candidate_revision_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True, unique=True
    )
    rollback_revision_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    candidate_paused: Mapped[bool] = mapped_column(Boolean(), nullable=False, default=False)
    consecutive_failures: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    promotion_observation_remaining: Mapped[int] = mapped_column(
        Integer(), nullable=False, default=0
    )
    created_by: Mapped[str] = mapped_column(String(32), nullable=False)
    last_evaluated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    @property
    def satisfaction_rate(self) -> float | None:
        rated = self.success_count + self.failure_count
        return self.success_count / rated if rated else None


class SkillRevision(Base):
    __tablename__ = "skill_revisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    skill_id: Mapped[str] = mapped_column(
        ForeignKey("skills.id", ondelete="CASCADE"), nullable=False, index=True
    )
    previous_revision_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    operation: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(Text(), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text(), nullable=True)
    expected_improvement: Mapped[str | None] = mapped_column(Text(), nullable=True)
    source_turn_ids_json: Mapped[str] = mapped_column(Text(), nullable=False, default="[]")
    cognitive_job_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    created_by: Mapped[str] = mapped_column(String(32), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(250), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    promoted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    @property
    def source_turn_ids(self) -> list[str]:
        value = json.loads(self.source_turn_ids_json)
        return value if isinstance(value, list) else []


class SkillUsage(Base):
    __tablename__ = "skill_usage"
    __table_args__ = (
        UniqueConstraint("turn_id", "skill_revision_id", name="uq_skill_usage_turn_revision"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    skill_id: Mapped[str] = mapped_column(
        ForeignKey("skills.id", ondelete="CASCADE"), nullable=False, index=True
    )
    skill_revision_id: Mapped[str] = mapped_column(
        ForeignKey("skill_revisions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    turn_id: Mapped[str] = mapped_column(
        ForeignKey("turns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    result: Mapped[str] = mapped_column(String(32), nullable=False)
    feedback: Mapped[str | None] = mapped_column(String(20), nullable=True)
    objective_passed: Mapped[bool | None] = mapped_column(Boolean(), nullable=True)
    input_tokens: Mapped[int] = mapped_column(BigInteger(), nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(BigInteger(), nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class SkillEvolutionEvent(Base):
    __tablename__ = "skill_evolution_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    skill_id: Mapped[str] = mapped_column(
        ForeignKey("skills.id", ondelete="CASCADE"), nullable=False, index=True
    )
    revision_id: Mapped[str | None] = mapped_column(
        ForeignKey("skill_revisions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    cognitive_job_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    reason: Mapped[str | None] = mapped_column(Text(), nullable=True)
    evidence_json: Mapped[str] = mapped_column(Text(), nullable=False, default="{}")
    idempotency_key: Mapped[str] = mapped_column(String(250), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    @property
    def evidence(self) -> dict[str, object]:
        value = json.loads(self.evidence_json)
        return value if isinstance(value, dict) else {}
