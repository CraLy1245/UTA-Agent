from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MemoryDeltaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    revision_id: str
    source_turn_id: str
    raw_content: str
    delta_type: str
    priority: int
    status: str
    char_count: int
    consumed_by_job_id: str | None
    created_at: datetime


class MemoryStatusRead(BaseModel):
    active_delta_char_count: int
    delta_char_limit: int
    deferred_delta_char_count: int
    pending_count: int
    deferred_count: int
    formal_memory_char_count: int
    formal_memory_char_limit: int
    current_memory_version: int | None


class MemoryItemCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=18_000)
    category: str = Field(default="general", min_length=1, max_length=50)
    tags: list[str] = Field(default_factory=list, max_length=20)
    priority: int = Field(default=50, ge=0, le=100)


class MemoryItemUpdate(BaseModel):
    expected_revision_id: str
    title: str | None = Field(default=None, min_length=1, max_length=200)
    content: str | None = Field(default=None, min_length=1, max_length=18_000)
    category: str | None = Field(default=None, min_length=1, max_length=50)
    tags: list[str] | None = Field(default=None, max_length=20)
    priority: int | None = Field(default=None, ge=0, le=100)


class MemoryItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    category: str
    title: str
    content: str
    tags: list[str]
    priority: int
    status: str
    locked: bool
    current_revision_id: str
    char_count: int
    created_at: datetime
    updated_at: datetime


class MemoryRevisionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    memory_item_id: str
    previous_revision_id: str | None
    operation: str
    title: str
    content: str
    category: str
    priority: int
    status: str
    locked: bool
    source_turn_ids: list[str]
    cognitive_job_id: str | None
    created_by: str
    reason: str | None
    created_at: datetime


class CognitiveJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    job_type: str
    start_turn_number: int
    end_turn_number: int
    status: str
    memory_version_before: int
    memory_version_after: int | None
    attempt_count: int
    error_message: str | None
    result_json: str | None
    next_attempt_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
