from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import ApiError
from app.models import DatasetSnapshot, Project, Question, Sample, SeedSample


def project_or_404(project_id: str, db: Session = Depends(get_db)) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise ApiError(404, "NOT_FOUND", "Project not found")
    return project


def question_or_404(
    project_id: str,
    question_id: str,
    db: Session = Depends(get_db),
) -> Question:
    question = db.get(Question, question_id)
    if question is None or question.project_id != project_id:
        raise ApiError(404, "NOT_FOUND", "Question not found")
    return question


def seed_or_404(seed_id: str, db: Session = Depends(get_db)) -> SeedSample:
    seed = db.get(SeedSample, seed_id)
    if seed is None:
        raise ApiError(404, "NOT_FOUND", "Seed sample not found")
    return seed


def sample_or_404(sample_id: str, db: Session = Depends(get_db)) -> Sample:
    sample = db.get(Sample, sample_id)
    if sample is None:
        raise ApiError(404, "NOT_FOUND", "Sample not found")
    return sample


def snapshot_or_404(snapshot_id: str, db: Session = Depends(get_db)) -> DatasetSnapshot:
    snapshot = db.get(DatasetSnapshot, snapshot_id)
    if snapshot is None:
        raise ApiError(404, "NOT_FOUND", "Dataset snapshot not found")
    return snapshot
