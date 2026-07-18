from functools import lru_cache

from pydantic import AliasChoices, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Survival Agent API"
    environment: str = "development"
    database_url: str = "sqlite:///./data/survival_agent.db"
    cors_origins: list[str] = ["http://localhost:5173"]
    openai_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("OPENAI_API_KEY", "SURVIVAL_AGENT_OPENAI_API_KEY"),
    )
    workspace_path: str = "./workspace"
    tools_enabled: bool = True
    tool_read_max_bytes: int = 1_000_000
    tool_list_max_entries: int = 500
    tool_timeout_seconds: int = 2048
    turn_timeout_seconds: int = 1800
    max_model_loops: int = 9999

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="SURVIVAL_AGENT_",
        extra="ignore",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> object:
        if isinstance(value, str) and not value.startswith("["):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
