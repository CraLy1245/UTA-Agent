from datetime import datetime

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field


class ModelSettingUpdate(BaseModel):
    base_url: AnyHttpUrl
    model: str = Field(min_length=1, max_length=200)
    timeout_seconds: int = Field(ge=1, le=1800)
    max_output_tokens: int = Field(ge=1, le=1_000_000)
    temperature: float | None = Field(default=None, ge=0, le=2)
    enabled: bool = True


class ModelSettingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    role: str
    base_url: str
    model: str
    timeout_seconds: int
    max_output_tokens: int
    temperature: float | None
    api_key_env: str
    enabled: bool
    has_api_key: bool
    updated_at: datetime


class ModelListRead(BaseModel):
    models: list[str]
