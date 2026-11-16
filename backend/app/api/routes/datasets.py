from __future__ import annotations

from contextlib import suppress
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import project_or_404, snapshot_or_404
from app.api.serializers import snapshot_out
from app.core.database import get_db
from app.core.errors import ApiError
from app.models import DatasetSnapshot, EvaluationRun, Project, TrainingJob
from app.schemas.common import Message
from app.schemas.dataset import DatasetSnapshotOut
from app.services.datasets.exporter import freeze_snapshot

router = APIRouter(tags=["datasets"])


@router.post(
    "/projects/{project_id}/datasets",
    response_model=DatasetSnapshotOut,
    status_code=status.HTTP_201_CREATED,
)
def create_snapshot(
    project: Project = Depends(project_or_404),
    db: Session = Depends(get_db),
) -> DatasetSnapshotOut:
    snapshot = freeze_snapshot(db, project, list(project.questions))
    return snapshot_out(snapshot)


@router.get("/datasets", response_model=list[DatasetSnapshotOut])
def list_snapshots(
    project_id: str | None = Query(default=None, alias="projectId"),
    db: Session = Depends(get_db),
) -> list[DatasetSnapshotOut]:
    query = select(DatasetSnapshot)
    if project_id:
        query = query.where(DatasetSnapshot.project_id == project_id)
    snapshots = db.scalars(query.order_by(DatasetSnapshot.created_at.desc())).all()
    return [snapshot_out(snapshot) for snapshot in snapshots]


@router.get("/datasets/{snapshot_id}", response_model=DatasetSnapshotOut)
def get_snapshot(
    snapshot: DatasetSnapshot = Depends(snapshot_or_404),
) -> DatasetSnapshotOut:
    return snapshot_out(snapshot)


@router.delete("/datasets/{snapshot_id}", response_model=Message)
def delete_snapshot(
    snapshot: DatasetSnapshot = Depends(snapshot_or_404),
    db: Session = Depends(get_db),
) -> Message:
    active_training = db.scalar(
        select(TrainingJob.id)
        .where(
            TrainingJob.snapshot_id == snapshot.id,
            TrainingJob.status.in_(["pending", "running"]),
        )
        .limit(1)
    )
    active_evaluation = db.scalar(
        select(EvaluationRun.id)
        .where(
            EvaluationRun.snapshot_id == snapshot.id,
            EvaluationRun.status.in_(["pending", "running"]),
        )
        .limit(1)
    )
    if active_training or active_evaluation:
        raise ApiError(
            409,
            "SNAPSHOT_IN_USE",
            "Cancel active training or evaluation jobs before deleting this snapshot",
        )

    paths = {
        Path(snapshot.canonical_path),
        Path(snapshot.laya_path),
        *([Path(snapshot.gliner_path)] if snapshot.gliner_path else []),
    }
    parents = {path.parent for path in paths}
    db.delete(snapshot)
    db.commit()
    for path in paths:
        with suppress(OSError):
            path.unlink(missing_ok=True)
    for parent in parents:
        with suppress(OSError):
            parent.rmdir()
    return Message(message="Dataset snapshot deleted")


@router.get("/datasets/{snapshot_id}/download")
def download_snapshot(
    format: Literal["canonical", "laya", "gliner"] = Query(default="canonical"),
    snapshot: DatasetSnapshot = Depends(snapshot_or_404),
) -> FileResponse:
    paths = {
        "canonical": snapshot.canonical_path,
        "laya": snapshot.laya_path,
        "gliner": snapshot.gliner_path,
    }
    selected = paths[format]
    if not selected:
        raise ApiError(404, "NOT_FOUND", f"{format.capitalize()} export is not available")
    path = Path(selected)
    if not path.exists():
        raise ApiError(404, "NOT_FOUND", "Dataset file is missing from disk")
    return FileResponse(
        path,
        media_type="application/x-ndjson",
        filename=f"{snapshot.project_id[:8]}-v{snapshot.version}-{format}.jsonl",
    )
