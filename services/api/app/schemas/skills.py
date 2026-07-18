from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SkillCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=500)
    content: str = Field(min_length=1, max_length=4000)
    source_turn_ids: list[str] = Field(default_factory=list)
    reason: str = Field(default="Created by user", max_length=1000)


class SkillUpdate(BaseModel):
    expected_revision_id: str
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, min_length=1, max_length=500)
    content: str = Field(min_length=1, max_length=4000)
    reason: str = Field(default="Updated by user", max_length=1000)


class SkillRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str
    content: str
    status: str
    locked: bool
    use_count: int
    success_count: int
    failure_count: int
    selection_weight: float
    confidence_score: float
    exploration_rate: float
    stable_revision_id: str
    candidate_revision_id: str | None
    rollback_revision_id: str | None
    candidate_paused: bool
    consecutive_failures: int
    promotion_observation_remaining: int
    satisfaction_rate: float | None
    created_by: str
    last_evaluated_at: datetime | None
    created_at: datetime
    updated_at: datetime


class SkillRevisionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    skill_id: str
    previous_revision_id: str | None
    operation: str
    status: str
    name: str
    description: str
    content: str
    reason: str | None
    expected_improvement: str | None
    source_turn_ids: list[str]
    cognitive_job_id: str | None
    created_by: str
    created_at: datetime
    promoted_at: datetime | None


class SkillUsageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    skill_id: str
    skill_revision_id: str
    turn_id: str
    result: str
    feedback: str | None
    objective_passed: bool | None
    input_tokens: int
    output_tokens: int
    created_at: datetime


class SkillEvolutionEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    skill_id: str
    revision_id: str | None
    cognitive_job_id: str | None
    event_type: str
    reason: str | None
    evidence: dict[str, object]
    created_at: datetime


class CandidateAction(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)


class CandidateCreate(BaseModel):
    base_revision_id: str
    content: str = Field(min_length=1, max_length=4000)
    source_turn_ids: list[str] = Field(min_length=1)
    reason: str = Field(min_length=1, max_length=1000)
    expected_improvement: str = Field(min_length=1, max_length=1000)


class SkillEvolutionRead(BaseModel):
    skill: SkillRead
    revisions: list[SkillRevisionRead]
    usages: list[SkillUsageRead]
    events: list[SkillEvolutionEventRead]
