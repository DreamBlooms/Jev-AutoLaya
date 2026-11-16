from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import project_or_404
from app.api.serializers import project_out
from app.core.database import get_db
from app.models import Project
from app.schemas.common import Message
from app.schemas.project import ProjectCreate, ProjectOut, ProjectUpdate

router = APIRouter(tags=["projects"])


@router.post("/projects", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)) -> ProjectOut:
    project = Project(
        name=payload.name,
        domain=payload.domain,
        languages=payload.languages,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project_out(project)


@router.get("/projects", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_db)) -> list[ProjectOut]:
    projects = db.scalars(select(Project).order_by(Project.created_at.desc())).all()
    return [project_out(project) for project in projects]


@router.get("/projects/{project_id}", response_model=ProjectOut)
def get_project(project: Project = Depends(project_or_404)) -> ProjectOut:
    return project_out(project)


@router.put("/projects/{project_id}", response_model=ProjectOut)
def update_project(
    payload: ProjectUpdate,
    project: Project = Depends(project_or_404),
    db: Session = Depends(get_db),
) -> ProjectOut:
    if payload.name is not None:
        project.name = payload.name
    if payload.domain is not None:
        project.domain = payload.domain
    if payload.languages is not None:
        project.languages = payload.languages
    db.commit()
    db.refresh(project)
    return project_out(project)


@router.post("/projects/{project_id}/delete", response_model=Message)
def delete_project(
    project: Project = Depends(project_or_404),
    db: Session = Depends(get_db),
) -> Message:
    db.delete(project)
    db.commit()
    return Message(message="Project deleted")


@router.delete("/projects/{project_id}", response_model=Message)
def delete_project_rest(
    project: Project = Depends(project_or_404),
    db: Session = Depends(get_db),
) -> Message:
    db.delete(project)
    db.commit()
    return Message(message="Project deleted")
