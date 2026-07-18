from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from services.agent.model_provider import OpenAICompatibleProvider, ProviderConfig, ProviderError
from services.api.app.core.config import get_settings
from services.api.app.core.security import redact_text
from services.api.app.db.models import ModelSetting
from services.api.app.db.session import get_db
from services.api.app.schemas.model_settings import (
    ModelListRead,
    ModelSettingRead,
    ModelSettingUpdate,
)

router = APIRouter(prefix="/model-settings", tags=["model-settings"])
SessionDep = Annotated[Session, Depends(get_db)]


def _serialize(setting: ModelSetting) -> ModelSettingRead:
    return ModelSettingRead(
        role=setting.role,
        base_url=setting.base_url,
        model=setting.model,
        timeout_seconds=setting.timeout_seconds,
        max_output_tokens=setting.max_output_tokens,
        temperature=setting.temperature,
        api_key_env=setting.api_key_env,
        enabled=setting.enabled,
        has_api_key=get_settings().openai_api_key is not None,
        updated_at=setting.updated_at,
    )


@router.get("/{role}", response_model=ModelSettingRead)
def get_model_setting(role: str, db: SessionDep) -> ModelSettingRead:
    setting = db.get(ModelSetting, role)
    if setting is None:
        raise HTTPException(status_code=404, detail="Model setting not found")
    return _serialize(setting)


@router.get("/{role}/models", response_model=ModelListRead)
async def list_provider_models(role: str, db: SessionDep) -> ModelListRead:
    setting = db.get(ModelSetting, role)
    if setting is None:
        raise HTTPException(status_code=404, detail="Model setting not found")
    secret = get_settings().openai_api_key
    if secret is None or not secret.get_secret_value():
        raise HTTPException(status_code=409, detail=f"Set {setting.api_key_env} first")
    provider = OpenAICompatibleProvider(
        ProviderConfig(
            base_url=setting.base_url,
            api_key=secret.get_secret_value(),
            model=setting.model,
            timeout_seconds=setting.timeout_seconds,
            max_output_tokens=setting.max_output_tokens,
            temperature=setting.temperature,
        )
    )
    try:
        return ModelListRead(models=await provider.list_models())
    except ProviderError as exc:
        raise HTTPException(status_code=502, detail=redact_text(str(exc))) from exc


@router.put("/{role}", response_model=ModelSettingRead)
def update_model_setting(
    role: str, payload: ModelSettingUpdate, db: SessionDep
) -> ModelSettingRead:
    setting = db.get(ModelSetting, role)
    if setting is None:
        raise HTTPException(status_code=404, detail="Model setting not found")
    setting.base_url = str(payload.base_url).rstrip("/")
    setting.model = payload.model.strip()
    setting.timeout_seconds = payload.timeout_seconds
    setting.max_output_tokens = payload.max_output_tokens
    setting.temperature = payload.temperature
    setting.enabled = payload.enabled
    db.commit()
    db.refresh(setting)
    return _serialize(setting)
