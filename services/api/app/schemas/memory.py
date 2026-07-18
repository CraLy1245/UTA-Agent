from datetime import datetime

from pydantic import BaseModel, ConfigDict


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
