import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from services.api.app.api.cognitive_jobs import router as cognitive_jobs_router
from services.api.app.api.conversations import router as conversations_router
from services.api.app.api.conversations import turn_router
from services.api.app.api.data import router as data_router
from services.api.app.api.health import router as health_router
from services.api.app.api.memory import router as memory_router
from services.api.app.api.model_settings import router as model_settings_router
from services.api.app.api.skills import router as skills_router
from services.api.app.api.survival import router as survival_router
from services.api.app.api.survival import turn_router as survival_turn_router
from services.api.app.api.tools import router as tools_router
from services.api.app.api.websocket import router as websocket_router
from services.api.app.core.config import get_settings
from services.api.app.core.logging import configure_logging
from services.api.app.db.session import SessionLocal, engine
from services.memory.cognitive import cognitive_worker, recover_unfinished_jobs


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    with engine.connect() as connection:
        connection.exec_driver_sql("SELECT 1")
    with SessionLocal() as db:
        # A fresh process cannot have a live claim from its previous Worker.
        recovered = recover_unfinished_jobs(db, stale_after_seconds=0)
        db.commit()
    logging.getLogger("survival.app").info("application started; recovered_jobs=%s", recovered)
    worker_task = asyncio.create_task(cognitive_worker.run())
    yield
    cognitive_worker.stop()
    await worker_task
    engine.dispose()


settings = get_settings()
configure_logging(settings.log_directory)
app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)


@app.exception_handler(OperationalError)
async def handle_database_busy(_: Request, exc: OperationalError) -> JSONResponse:
    logging.getLogger("survival.error").error("database operation failed: %s", type(exc).__name__)
    busy = "locked" in str(exc).lower() or "busy" in str(exc).lower()
    return JSONResponse(
        status_code=503 if busy else 500,
        content={"detail": "Database is busy; retry the request" if busy else "Database error"},
        headers={"Retry-After": "1"} if busy else None,
    )


@app.exception_handler(SQLAlchemyError)
async def handle_database_error(_: Request, exc: SQLAlchemyError) -> JSONResponse:
    logging.getLogger("survival.error").error("database operation failed: %s", type(exc).__name__)
    return JSONResponse(status_code=500, content={"detail": "Database error"})
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)
app.include_router(health_router, prefix="/api")
app.include_router(memory_router, prefix="/api")
app.include_router(cognitive_jobs_router, prefix="/api")
app.include_router(data_router, prefix="/api")
app.include_router(conversations_router, prefix="/api")
app.include_router(turn_router, prefix="/api")
app.include_router(model_settings_router, prefix="/api")
app.include_router(skills_router, prefix="/api")
app.include_router(survival_router, prefix="/api")
app.include_router(survival_turn_router, prefix="/api")
app.include_router(tools_router, prefix="/api")
app.include_router(websocket_router, prefix="/api")
