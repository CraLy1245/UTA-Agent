from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.api.app.api.conversations import router as conversations_router
from services.api.app.api.conversations import turn_router
from services.api.app.api.health import router as health_router
from services.api.app.api.model_settings import router as model_settings_router
from services.api.app.api.tools import router as tools_router
from services.api.app.api.websocket import router as websocket_router
from services.api.app.core.config import get_settings
from services.api.app.db.session import engine


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    with engine.connect() as connection:
        connection.exec_driver_sql("SELECT 1")
    yield
    engine.dispose()


settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["*"],
)
app.include_router(health_router, prefix="/api")
app.include_router(conversations_router, prefix="/api")
app.include_router(turn_router, prefix="/api")
app.include_router(model_settings_router, prefix="/api")
app.include_router(tools_router, prefix="/api")
app.include_router(websocket_router, prefix="/api")
