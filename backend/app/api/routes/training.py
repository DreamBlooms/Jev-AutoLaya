from __future__ import annotations

import contextlib
import json
import os
import signal
import time
from collections.abc import Iterator

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, get_db
from app.core.errors import ApiError
from app.models import Project, TrainingJob
from app.schemas.jobs import TrainingChartsOut, TrainingJobOut, TrainingRequest
from app.services.training.charts import build_training_charts
from app.services.training.runner import create_training_job

router = APIRouter(tags=["training"])
TERMINAL = {"completed", "failed", "cancelled"}


@router.post(
    "/training-jobs",
    response_model=TrainingJobOut,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_training(
    payload: TrainingRequest,
    db: Session = Depends(get_db),
) -> TrainingJob:
    project = db.get(Project, payload.project_id)
    if project is None:
        raise ApiError(404, "NOT_FOUND", "Project not found")
    return create_training_job(db, project, payload)


@router.get("/training-jobs", response_model=list[TrainingJobOut])
def list_training_jobs(
    project_id: str | None = Query(default=None, alias="projectId"),
    db: Session = Depends(get_db),
) -> list[TrainingJob]:
    query = select(TrainingJob)
    if project_id:
        query = query.where(TrainingJob.project_id == project_id)
    return list(db.scalars(query.order_by(TrainingJob.created_at.desc()).limit(100)))


@router.get("/training-jobs/{job_id}", response_model=TrainingJobOut)
def get_training_job(job_id: str, db: Session = Depends(get_db)) -> TrainingJob:
    job = db.get(TrainingJob, job_id)
    if job is None:
        raise ApiError(404, "NOT_FOUND", "Training job not found")
    return job


@router.get("/training-jobs/{job_id}/charts", response_model=TrainingChartsOut)
def training_charts(job_id: str, db: Session = Depends(get_db)) -> TrainingChartsOut:
    job = db.get(TrainingJob, job_id)
    if job is None:
        raise ApiError(404, "NOT_FOUND", "Training job not found")
    return TrainingChartsOut(**build_training_charts(job))


@router.get("/training-jobs/{job_id}/events")
def training_events(job_id: str) -> StreamingResponse:
    def stream() -> Iterator[str]:
        while True:
            db = SessionLocal()
            try:
                job = db.get(TrainingJob, job_id)
                if job is None:
                    yield f"data: {json.dumps({'error': 'not_found'})}\n\n"
                    return
                payload = TrainingJobOut.model_validate(job).model_dump(by_alias=True, mode="json")
            finally:
                db.close()
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            if payload["status"] in TERMINAL:
                return
            time.sleep(1)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/training-jobs/{job_id}/cancel", response_model=TrainingJobOut)
def cancel_training_job(job_id: str, db: Session = Depends(get_db)) -> TrainingJob:
    job = db.get(TrainingJob, job_id)
    if job is None:
        raise ApiError(404, "NOT_FOUND", "Training job not found")
    if job.status in TERMINAL:
        return job
    job.cancel_requested = True
    if job.status == "pending":
        job.status = "cancelled"
        job.stage = "cancelled"
    db.commit()
    db.refresh(job)
    if job.pid:
        try:
            os.killpg(os.getpgid(job.pid), signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.kill(job.pid, signal.SIGTERM)
    return job
