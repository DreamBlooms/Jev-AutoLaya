from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import project_or_404, sample_or_404
from app.api.serializers import annotation_out, sample_detail, sample_out
from app.core.database import get_db
from app.core.errors import ApiError
from app.models import Annotation, Project, Question, Sample
from app.schemas.common import Message
from app.schemas.sample import (
    AcceptRequest,
    AnnotationOut,
    AnswerUpdate,
    RejectRequest,
    SampleCreate,
    SampleDetail,
    SampleImportResult,
    SampleOut,
)
from app.schemas.seed import SeedImport
from app.services.answers import normalize_answer
from app.services.sample_import import (
    csv_template,
    jsonl_template,
    parse_sample_file,
)
from app.services.teachers.jev import JevTeacher, JevTeacherError

router = APIRouter(tags=["samples"])
MAX_IMPORT_BYTES = 20 * 1024 * 1024


def _create_sample(payload: SampleCreate, project: Project, db: Session) -> Sample:
    by_key = {question.key: question for question in project.questions}
    unknown = [key for key in payload.labels if key not in by_key]
    if unknown:
        raise ApiError(
            422,
            "VALIDATION_ERROR",
            f"Sample contains unknown question keys: {', '.join(sorted(unknown))}",
        )
    sample = Sample(
        project_id=project.id,
        state=payload.state,
        meta=payload.meta,
        source=payload.source,
        language=payload.language,
        difficulty=payload.difficulty,
        status="pending",
    )
    db.add(sample)
    db.flush()
    for key, raw_answer in payload.labels.items():
        question = by_key[key]
        answer = normalize_answer(question, raw_answer)
        sample.annotations.append(
            Annotation(
                question_id=question.id,
                answer=answer,
                teacher="human",
                confidence=answer.get("confidence"),
                probabilities=answer.get("probabilities"),
                status="pending",
            )
        )
    db.commit()
    db.refresh(sample)
    return sample


@router.post(
    "/projects/{project_id}/samples",
    response_model=SampleDetail,
    status_code=status.HTTP_201_CREATED,
)
def create_sample(
    payload: SampleCreate,
    project: Project = Depends(project_or_404),
    db: Session = Depends(get_db),
) -> SampleDetail:
    sample = _create_sample(payload, project, db)
    return sample_detail(sample, list(project.questions))


@router.get("/projects/{project_id}/samples/template")
def download_sample_template(
    project: Project = Depends(project_or_404),
    template_format: Literal["jsonl", "csv"] = Query(default="jsonl", alias="format"),
) -> Response:
    if template_format == "csv":
        return Response(
            content=csv_template(),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="autolaya-samples-template.csv"'},
        )
    return Response(
        content=jsonl_template(),
        media_type="application/x-ndjson",
        headers={"Content-Disposition": 'attachment; filename="autolaya-samples-template.jsonl"'},
    )


@router.post(
    "/projects/{project_id}/samples/import",
    response_model=SampleImportResult,
    status_code=status.HTTP_201_CREATED,
)
def import_samples(
    file: UploadFile = File(...),
    project: Project = Depends(project_or_404),
    db: Session = Depends(get_db),
) -> SampleImportResult:
    filename = file.filename or ""
    content = file.file.read(MAX_IMPORT_BYTES + 1)
    if not content:
        raise ApiError(422, "VALIDATION_ERROR", "Uploaded file is empty")
    if len(content) > MAX_IMPORT_BYTES:
        raise ApiError(422, "VALIDATION_ERROR", "Uploaded file exceeds 20 MB")
    try:
        rows = parse_sample_file(
            filename,
            content,
            {question.key for question in project.questions},
        )
    except ValueError as exc:
        raise ApiError(422, "VALIDATION_ERROR", str(exc)) from exc
    samples = [_create_sample(row, project, db) for row in rows]
    return SampleImportResult(
        imported=len(samples),
        heldout=sum(1 for sample in samples if (sample.meta or {}).get("heldout")),
        samples=[sample_out(sample) for sample in samples],
    )


@router.post(
    "/projects/{project_id}/heldout",
    response_model=list[SampleOut],
    status_code=status.HTTP_201_CREATED,
)
def import_heldout_samples(
    payload: SeedImport,
    project: Project = Depends(project_or_404),
    db: Session = Depends(get_db),
) -> list[SampleOut]:
    samples = []
    for item in payload.samples:
        sample = _create_sample(
            SampleCreate(
                state=item.state,
                meta={"heldout": True, "source": "real-heldout"},
                labels=item.labels,
                source="real-heldout",
                language=item.language,
                difficulty="medium",
            ),
            project,
            db,
        )
        samples.append(sample_out(sample))
    return samples


@router.get("/samples", response_model=list[SampleOut])
def list_samples(
    status_filter: str | None = Query(default=None, alias="status"),
    project_id: str | None = Query(default=None, alias="projectId"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[SampleOut]:
    query = select(Sample).options(selectinload(Sample.annotations))
    if status_filter:
        query = query.where(Sample.status == status_filter)
    if project_id:
        query = query.where(Sample.project_id == project_id)
    query = query.order_by(Sample.created_at.asc()).limit(limit).offset(offset)
    samples = db.scalars(query).all()
    return [sample_out(sample) for sample in samples]


@router.get("/samples/{sample_id}", response_model=SampleDetail)
def get_sample(
    sample: Sample = Depends(sample_or_404),
    db: Session = Depends(get_db),
) -> SampleDetail:
    project = db.get(Project, sample.project_id)
    if project is None:
        raise ApiError(404, "NOT_FOUND", "Project not found")
    return sample_detail(sample, list(project.questions))


@router.delete("/samples/{sample_id}", response_model=Message)
@router.post("/samples/{sample_id}/delete", response_model=Message)
def delete_sample(
    sample: Sample = Depends(sample_or_404),
    db: Session = Depends(get_db),
) -> Message:
    db.delete(sample)
    db.commit()
    return Message(message="Sample deleted")


@router.post("/samples/{sample_id}/accept", response_model=SampleDetail)
def accept_sample(
    payload: AcceptRequest | None = None,
    sample: Sample = Depends(sample_or_404),
    db: Session = Depends(get_db),
) -> SampleDetail:
    project = db.get(Project, sample.project_id)
    if project is None:
        raise ApiError(404, "NOT_FOUND", "Project not found")
    questions = list(project.questions)
    if not questions:
        raise ApiError(422, "VALIDATION_ERROR", "Add at least one question before accepting")
    annotations = {annotation.question_id: annotation for annotation in sample.annotations}
    missing = [question.key for question in questions if question.id not in annotations]
    if missing:
        raise ApiError(
            422,
            "VALIDATION_ERROR",
            f"Missing answers for: {', '.join(missing)}",
            {"questionKeys": missing},
        )
    reviewer = payload.reviewer if payload else "human"
    note = payload.review_note if payload else None
    for annotation in sample.annotations:
        annotation.status = "accepted"
        annotation.reviewer = reviewer
        if note:
            annotation.review_note = note
    sample.status = "accepted"
    db.commit()
    db.refresh(sample)
    return sample_detail(sample, questions)


@router.post("/samples/{sample_id}/reject", response_model=SampleDetail)
def reject_sample(
    payload: RejectRequest | None = None,
    sample: Sample = Depends(sample_or_404),
    db: Session = Depends(get_db),
) -> SampleDetail:
    project = db.get(Project, sample.project_id)
    if project is None:
        raise ApiError(404, "NOT_FOUND", "Project not found")
    reviewer = payload.reviewer if payload else "human"
    note = payload.review_note if payload else None
    sample.status = "rejected"
    for annotation in sample.annotations:
        annotation.status = "rejected"
        annotation.reviewer = reviewer
        if note:
            annotation.review_note = note
    db.commit()
    db.refresh(sample)
    return sample_detail(sample, list(project.questions))


@router.put(
    "/samples/{sample_id}/annotations/{question_ref}",
    response_model=AnnotationOut,
)
def upsert_annotation(
    payload: AnswerUpdate,
    question_ref: str,
    sample: Sample = Depends(sample_or_404),
    db: Session = Depends(get_db),
) -> AnnotationOut:
    question = db.scalar(
        select(Question).where(
            Question.project_id == sample.project_id,
            or_(Question.id == question_ref, Question.key == question_ref),
        )
    )
    if question is None:
        raise ApiError(404, "NOT_FOUND", "Question not found")
    answer = normalize_answer(question, payload.answer)
    annotation = db.scalar(
        select(Annotation).where(
            Annotation.sample_id == sample.id,
            Annotation.question_id == question.id,
        )
    )
    if annotation is None:
        annotation = Annotation(sample_id=sample.id, question_id=question.id)
        db.add(annotation)
    annotation.answer = answer
    annotation.confidence = answer.get("confidence")
    annotation.probabilities = answer.get("probabilities")
    annotation.teacher = "human"
    annotation.teacher_model = None
    annotation.status = "accepted"
    annotation.reviewer = payload.reviewer
    annotation.review_note = payload.review_note
    db.commit()
    db.refresh(annotation)
    return annotation_out(annotation)


@router.post("/samples/{sample_id}/reannotate", response_model=SampleDetail)
def reannotate_sample(
    sample: Sample = Depends(sample_or_404),
    db: Session = Depends(get_db),
) -> SampleDetail:
    project = db.get(Project, sample.project_id)
    if project is None:
        raise ApiError(404, "NOT_FOUND", "Project not found")
    questions = list(project.questions)
    if not questions:
        raise ApiError(422, "VALIDATION_ERROR", "Add at least one question before reannotating")
    try:
        labels = JevTeacher().label(sample.state, questions)
    except JevTeacherError as exc:
        raise ApiError(400, "TEACHER_ERROR", str(exc)) from exc
    existing = {annotation.question_id: annotation for annotation in sample.annotations}
    for question in questions:
        label = labels.get(question.key)
        if label is None:
            continue
        annotation = existing.get(question.id)
        if annotation is None:
            annotation = Annotation(sample_id=sample.id, question_id=question.id)
            db.add(annotation)
            sample.annotations.append(annotation)
        annotation.answer = label["answer"]
        annotation.teacher = label["teacher"]
        annotation.teacher_model = label["teacher_model"]
        annotation.confidence = label["confidence"]
        annotation.probabilities = label["probabilities"]
        annotation.status = "pending"
        annotation.reviewer = None
        annotation.review_note = None
    sample.status = "pending"
    db.commit()
    db.refresh(sample)
    return sample_detail(sample, questions)
