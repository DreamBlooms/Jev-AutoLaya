from __future__ import annotations

import shutil
import tempfile
import zipfile
from pathlib import Path

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.background import BackgroundTask

from app.core.config import get_settings
from app.core.database import get_db
from app.core.errors import ApiError
from app.models import Deployment, ModelArtifact
from app.schemas.jobs import (
    DeploymentCreate,
    DeploymentOut,
    ModelArtifactOut,
)
from app.services.serving.runner import (
    create_deployment,
    restart_deployment,
    stop_deployment,
)

router = APIRouter(tags=["models"])


@router.get("/artifacts", response_model=list[ModelArtifactOut])
def list_artifacts(
    project_id: str | None = Query(default=None, alias="projectId"),
    target: str | None = Query(default=None),
    kind: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[ModelArtifact]:
    query = select(ModelArtifact)
    if project_id:
        query = query.where(ModelArtifact.project_id == project_id)
    if target:
        query = query.where(ModelArtifact.target == target)
    if kind:
        query = query.where(ModelArtifact.kind == kind)
    return list(db.scalars(query.order_by(ModelArtifact.created_at.desc()).limit(100)))


@router.get("/artifacts/{artifact_id}", response_model=ModelArtifactOut)
def get_artifact(artifact_id: str, db: Session = Depends(get_db)) -> ModelArtifact:
    artifact = db.get(ModelArtifact, artifact_id)
    if artifact is None:
        raise ApiError(404, "NOT_FOUND", "Model artifact not found")
    return artifact


@router.get("/artifacts/{artifact_id}/download")
def download_artifact(artifact_id: str, db: Session = Depends(get_db)) -> FileResponse:
    artifact = db.get(ModelArtifact, artifact_id)
    if artifact is None:
        raise ApiError(404, "NOT_FOUND", "Model artifact not found")
    path = Path(artifact.path)
    if not path.exists():
        raise ApiError(404, "NOT_FOUND", "Artifact files are missing from disk")
    download_root = get_settings().resolved_artifact_dir / ".downloads"
    download_root.mkdir(parents=True, exist_ok=True)
    temp_dir = Path(tempfile.mkdtemp(prefix="autolaya-artifact-", dir=download_root))
    archive = temp_dir / f"{artifact.target}-{artifact.id[:8]}.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_STORED) as bundle:
        if path.is_dir():
            for file_path in path.rglob("*"):
                if file_path.is_file():
                    bundle.write(file_path, file_path.relative_to(path.parent))
        else:
            bundle.write(path, path.name)
    return FileResponse(
        archive,
        media_type="application/zip",
        filename=archive.name,
        background=BackgroundTask(shutil.rmtree, temp_dir, ignore_errors=True),
    )


@router.delete("/artifacts/{artifact_id}")
def delete_artifact(artifact_id: str, db: Session = Depends(get_db)) -> dict[str, str]:
    artifact = db.get(ModelArtifact, artifact_id)
    if artifact is None:
        raise ApiError(404, "NOT_FOUND", "Model artifact not found")
    active = db.scalar(
        select(Deployment).where(
            Deployment.artifact_id == artifact_id,
            Deployment.status.in_(["starting", "running"]),
        )
    )
    if active is not None:
        raise ApiError(
            409,
            "DEPLOYMENT_ERROR",
            "Stop the active deployment before deleting this artifact",
        )
    db.delete(artifact)
    db.commit()
    return {"message": "Artifact deleted"}


@router.delete("/deployments/{deployment_id}")
def delete_deployment(deployment_id: str, db: Session = Depends(get_db)) -> dict[str, str]:
    deployment = db.get(Deployment, deployment_id)
    if deployment is None:
        raise ApiError(404, "NOT_FOUND", "Deployment not found")
    if deployment.status in {"starting", "running"}:
        stop_deployment(db, deployment)
    db.delete(deployment)
    db.commit()
    return {"message": "Deployment deleted"}


@router.post(
    "/deployments",
    response_model=DeploymentOut,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_deployment(
    payload: DeploymentCreate,
    db: Session = Depends(get_db),
) -> Deployment:
    return create_deployment(db, payload)


@router.get("/deployments", response_model=list[DeploymentOut])
def list_deployments(
    project_id: str | None = Query(default=None, alias="projectId"),
    db: Session = Depends(get_db),
) -> list[Deployment]:
    query = select(Deployment)
    if project_id:
        query = query.join(ModelArtifact).where(ModelArtifact.project_id == project_id)
    return list(db.scalars(query.order_by(Deployment.created_at.desc()).limit(100)))


@router.get("/deployments/{deployment_id}", response_model=DeploymentOut)
def get_deployment(deployment_id: str, db: Session = Depends(get_db)) -> Deployment:
    deployment = db.get(Deployment, deployment_id)
    if deployment is None:
        raise ApiError(404, "NOT_FOUND", "Deployment not found")
    return deployment


@router.post("/deployments/{deployment_id}/stop", response_model=DeploymentOut)
def stop(deployment_id: str, db: Session = Depends(get_db)) -> Deployment:
    deployment = db.get(Deployment, deployment_id)
    if deployment is None:
        raise ApiError(404, "NOT_FOUND", "Deployment not found")
    return stop_deployment(db, deployment)


@router.post("/deployments/{deployment_id}/restart", response_model=DeploymentOut)
def restart(deployment_id: str, db: Session = Depends(get_db)) -> Deployment:
    deployment = db.get(Deployment, deployment_id)
    if deployment is None:
        raise ApiError(404, "NOT_FOUND", "Deployment not found")
    return restart_deployment(db, deployment)
