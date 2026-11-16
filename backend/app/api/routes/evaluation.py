from __future__ import annotations

import json
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, get_db
from app.core.errors import ApiError
from app.models import EvaluationRun, Project
from app.schemas.jobs import EvaluationRequest, EvaluationRunOut
from app.services.evaluation.runner import create_evaluation_run

router = APIRouter(tags=["evaluation"])
TERMINAL = {"completed", "failed", "cancelled"}


@router.post(
    "/evaluations",
    response_model=EvaluationRunOut,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_evaluation(
    payload: EvaluationRequest,
    db: Session = Depends(get_db),
) -> EvaluationRun:
    project = db.get(Project, payload.project_id)
    if project is None:
        raise ApiError(404, "NOT_FOUND", "Project not found")
    return create_evaluation_run(db, project, payload)


@router.get("/evaluations", response_model=list[EvaluationRunOut])
def list_evaluations(
    project_id: str | None = Query(default=None, alias="projectId"),
    db: Session = Depends(get_db),
) -> list[EvaluationRun]:
    query = select(EvaluationRun)
    if project_id:
        query = query.where(EvaluationRun.project_id == project_id)
    return list(db.scalars(query.order_by(EvaluationRun.created_at.desc()).limit(100)))


@router.get("/evaluations/{run_id}", response_model=EvaluationRunOut)
def get_evaluation(run_id: str, db: Session = Depends(get_db)) -> EvaluationRun:
    run = db.get(EvaluationRun, run_id)
    if run is None:
        raise ApiError(404, "NOT_FOUND", "Evaluation run not found")
    return run


@router.get("/evaluations/{run_id}/events")
def evaluation_events(run_id: str) -> StreamingResponse:
    def stream() -> Iterator[str]:
        while True:
            db = SessionLocal()
            try:
                run = db.get(EvaluationRun, run_id)
                if run is None:
                    yield f"data: {json.dumps({'error': 'not_found'})}\n\n"
                    return
                payload = EvaluationRunOut.model_validate(run).model_dump(
                    by_alias=True, mode="json"
                )
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


@router.post("/evaluations/{run_id}/cancel", response_model=EvaluationRunOut)
def cancel_evaluation(run_id: str, db: Session = Depends(get_db)) -> EvaluationRun:
    run = db.get(EvaluationRun, run_id)
    if run is None:
        raise ApiError(404, "NOT_FOUND", "Evaluation run not found")
    if run.status in TERMINAL:
        return run
    run.cancel_requested = True
    if run.status == "pending":
        run.status = "cancelled"
        run.stage = "cancelled"
    db.commit()
    db.refresh(run)
    return run


@router.get("/evaluations/{run_id}/report")
def download_evaluation_report(
    run_id: str,
    format: Literal["json", "md"] = Query(default="json"),
    db: Session = Depends(get_db),
) -> FileResponse:
    run = db.get(EvaluationRun, run_id)
    if run is None or not run.report_path:
        raise ApiError(404, "NOT_FOUND", "Evaluation report not available")
    path = Path(run.report_path)
    if format == "md":
        path = path.with_suffix(".md")
    if not path.exists():
        raise ApiError(404, "NOT_FOUND", "Evaluation report file is missing")
    return FileResponse(path, filename=f"evaluation-{run.id[:8]}.{format}")
