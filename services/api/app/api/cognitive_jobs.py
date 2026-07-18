from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from services.api.app.db.models import CognitiveJob
from services.api.app.db.session import get_db
from services.api.app.schemas.memory import CognitiveJobRead
from services.memory.cognitive import cognitive_worker

router = APIRouter(prefix="/cognitive-jobs", tags=["cognitive-jobs"])
SessionDep = Annotated[Session, Depends(get_db)]


@router.get("", response_model=list[CognitiveJobRead])
def list_jobs(db: SessionDep, status: str | None = None) -> list[CognitiveJob]:
    statement = select(CognitiveJob)
    if status:
        statement = statement.where(CognitiveJob.status == status)
    return list(db.scalars(statement.order_by(CognitiveJob.created_at.desc())))


@router.get("/{job_id}", response_model=CognitiveJobRead)
def get_job(job_id: str, db: SessionDep) -> CognitiveJob:
    job = db.get(CognitiveJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Cognitive job not found")
    return job


@router.post("/{job_id}/retry", response_model=CognitiveJobRead)
def retry_job(job_id: str, db: SessionDep) -> CognitiveJob:
    db.connection().exec_driver_sql("BEGIN IMMEDIATE")
    job = db.get(CognitiveJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Cognitive job not found")
    if job.status not in {"failed", "conflict"}:
        raise HTTPException(status_code=409, detail="Only failed or conflicted jobs can be retried")
    job.status = "pending"
    job.next_attempt_at = None
    job.error_message = None
    db.commit()
    db.refresh(job)
    return job


@router.post("/run", status_code=202)
async def run_one_job() -> dict[str, bool]:
    return {"worked": await cognitive_worker.run_once()}
