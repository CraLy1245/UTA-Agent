from typing import Literal

from pydantic import BaseModel


class DatabaseHealth(BaseModel):
    status: Literal["healthy"]
    engine: Literal["sqlite"]
    journal_mode: str


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str
    environment: str
    database: DatabaseHealth
