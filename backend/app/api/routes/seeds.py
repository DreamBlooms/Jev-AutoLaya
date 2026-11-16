from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import project_or_404, seed_or_404
from app.api.serializers import sample_detail, sample_out
from app.core.database import get_db
from app.core.errors import ApiError
from app.models import Annotation, Project, Sample, SeedSample
from app.schemas.common import Message
from app.schemas.sample import SampleDetail, SampleOut
from app.schemas.seed import (
    SeedCreate,
    SeedImport,
    SeedImportResult,
    SeedOut,
    SeedPromoteRequest,
)
from app.services.answers import normalize_answer
from app.services.sample_import import csv_seed_template, jsonl_seed_template, parse_seed_file

router = APIRouter(tags=["seeds"])
MAX_IMPORT_BYTES = 20 * 1024 * 1024


def _promote_seed(seed: SeedSample, project: Project, db: Session) -> Sample:
    questions = list(project.questions)
    by_key = {question.key: question for question in questions}
    unknown = [key for key in seed.labels if key not in by_key]
    if unknown:
        raise ApiError(
            422,
            "VALIDATION_ERROR",
            f"Seed contains unknown question keys: {', '.join(sorted(unknown))}",
        )
    sample = Sample(
        project_id=project.id,
        state=seed.state,
        meta={"seedId": seed.id, "seedSource": seed.source},
        source="seed",
        language=seed.language,
        difficulty="medium",
        status="pending",
    )
    db.add(sample)
    db.flush()
    for key, raw_answer in seed.labels.items():
        question = by_key[key]
        answer = normalize_answer(question, raw_answer)
        sample.annotations.append(
            Annotation(
                question_id=question.id,
                answer=answer,
                teacher="human",
                teacher_model=None,
                confidence=answer.get("confidence"),
                probabilities=answer.get("probabilities"),
                status="pending",
            )
        )
    db.commit()
    db.refresh(sample)
    return sample


@router.post(
    "/projects/{project_id}/seeds",
    response_model=list[SeedOut],
    status_code=status.HTTP_201_CREATED,
)
def import_seeds(
    payload: SeedImport,
    project: Project = Depends(project_or_404),
    db: Session = Depends(get_db),
) -> list[SeedSample]:
    seeds = [
        SeedSample(
            project_id=project.id,
            state=item.state,
            labels=item.labels,
            source=item.source,
            language=item.language,
        )
        for item in payload.samples
    ]
    db.add_all(seeds)
    db.commit()
    for seed in seeds:
        db.refresh(seed)
    return seeds


@router.get("/projects/{project_id}/seeds", response_model=list[SeedOut])
def list_seeds(project: Project = Depends(project_or_404)) -> list[SeedSample]:
    return list(project.seeds)


@router.get("/projects/{project_id}/seeds/template")
def download_seed_template(
    project: Project = Depends(project_or_404),
    template_format: Literal["jsonl", "csv"] = Query(default="jsonl", alias="format"),
) -> Response:
    if template_format == "csv":
        return Response(
            content=csv_seed_template(),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="autolaya-seeds-template.csv"'},
        )
    return Response(
        content=jsonl_seed_template(),
        media_type="application/x-ndjson",
        headers={"Content-Disposition": 'attachment; filename="autolaya-seeds-template.jsonl"'},
    )


@router.post(
    "/projects/{project_id}/seeds/import",
    response_model=SeedImportResult,
    status_code=status.HTTP_201_CREATED,
)
def import_seed_file(
    file: UploadFile = File(...),
    project: Project = Depends(project_or_404),
    db: Session = Depends(get_db),
) -> SeedImportResult:
    filename = file.filename or ""
    content = file.file.read(MAX_IMPORT_BYTES + 1)
    if not content:
        raise ApiError(422, "VALIDATION_ERROR", "Uploaded file is empty")
    if len(content) > MAX_IMPORT_BYTES:
        raise ApiError(422, "VALIDATION_ERROR", "Uploaded file exceeds 20 MB")
    try:
        rows = parse_seed_file(
            filename,
            content,
            {question.key for question in project.questions},
        )
    except ValueError as exc:
        raise ApiError(422, "VALIDATION_ERROR", str(exc)) from exc
    seeds = [
        SeedSample(
            project_id=project.id,
            state=row.state,
            labels=row.labels,
            source=row.source,
            language=row.language,
        )
        for row in rows
    ]
    db.add_all(seeds)
    db.commit()
    for seed in seeds:
        db.refresh(seed)
    return SeedImportResult(imported=len(seeds), seeds=seeds)


@router.delete("/seeds/{seed_id}", response_model=Message)
def delete_seed(
    seed: SeedSample = Depends(seed_or_404),
    db: Session = Depends(get_db),
) -> Message:
    db.delete(seed)
    db.commit()
    return Message(message="Seed deleted")


@router.post("/seeds/{seed_id}/promote", response_model=SampleDetail)
def promote_seed(
    seed: SeedSample = Depends(seed_or_404),
    db: Session = Depends(get_db),
) -> SampleDetail:
    project = db.get(Project, seed.project_id)
    if project is None:
        raise ApiError(404, "NOT_FOUND", "Project not found")
    sample = _promote_seed(seed, project, db)
    return sample_detail(sample, list(project.questions))


@router.post("/projects/{project_id}/seeds/promote", response_model=list[SampleOut])
def promote_seeds(
    payload: SeedPromoteRequest,
    project: Project = Depends(project_or_404),
    db: Session = Depends(get_db),
) -> list[SampleOut]:
    query = select(SeedSample).where(SeedSample.project_id == project.id)
    if payload.seed_ids:
        query = query.where(SeedSample.id.in_(payload.seed_ids))
    seeds = db.scalars(query.order_by(SeedSample.created_at)).all()
    if not seeds:
        raise ApiError(422, "VALIDATION_ERROR", "No seeds selected")
    samples = [_promote_seed(seed, project, db) for seed in seeds]
    return [sample_out(sample) for sample in samples]


@router.post("/projects/{project_id}/seeds/quick", response_model=SeedOut, status_code=201)
def quick_seed(
    payload: SeedCreate,
    project: Project = Depends(project_or_404),
    db: Session = Depends(get_db),
) -> SeedSample:
    seed = SeedSample(
        project_id=project.id,
        state=payload.state,
        labels=payload.labels,
        source=payload.source,
        language=payload.language,
    )
    db.add(seed)
    db.commit()
    db.refresh(seed)
    return seed
