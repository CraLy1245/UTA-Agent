from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from services.api.app.core.config import Settings, get_settings
from services.api.app.db.session import get_db
from services.api.app.schemas.health import DatabaseHealth, HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health_check(
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> HealthResponse:
    db.execute(text("SELECT 1"))
    journal_mode = db.execute(text("PRAGMA journal_mode")).scalar_one()
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        environment=settings.environment,
        database=DatabaseHealth(
            status="healthy",
            engine="sqlite",
            journal_mode=str(journal_mode).lower(),
        ),
    )
