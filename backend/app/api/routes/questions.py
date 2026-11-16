from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import project_or_404, question_or_404
from app.core.database import get_db
from app.core.errors import ApiError
from app.models import Project, Question
from app.schemas.common import Message
from app.schemas.question import QuestionCreate, QuestionOut, QuestionUpdate
from app.services.questions import validate_question_fields

router = APIRouter(tags=["questions"])


def _ensure_unique_key(
    db: Session,
    project_id: str,
    key: str,
    exclude_id: str | None = None,
) -> None:
    query = select(Question).where(Question.project_id == project_id, Question.key == key)
    existing = db.scalar(query)
    if existing is not None and existing.id != exclude_id:
        raise ApiError(422, "VALIDATION_ERROR", f"Question key already exists: {key}")


@router.post(
    "/projects/{project_id}/questions",
    response_model=QuestionOut,
    status_code=status.HTTP_201_CREATED,
)
def create_question(
    payload: QuestionCreate,
    project: Project = Depends(project_or_404),
    db: Session = Depends(get_db),
) -> QuestionOut:
    _ensure_unique_key(db, project.id, payload.key)
    order = payload.order
    if order == 0 and project.questions:
        order = max(question.order for question in project.questions) + 1
    question = Question(
        project_id=project.id,
        key=payload.key,
        type=payload.type,
        instructions=payload.instructions,
        criteria=payload.criteria,
        order=order,
    )
    db.add(question)
    db.commit()
    db.refresh(question)
    return question


@router.get("/projects/{project_id}/questions", response_model=list[QuestionOut])
def list_questions(project: Project = Depends(project_or_404)) -> list[Question]:
    return list(project.questions)


@router.put("/projects/{project_id}/questions/{question_id}", response_model=QuestionOut)
def update_question(
    payload: QuestionUpdate,
    question: Question = Depends(question_or_404),
    db: Session = Depends(get_db),
) -> Question:
    fields = payload.model_fields_set
    if payload.key is not None and payload.key != question.key:
        _ensure_unique_key(db, question.project_id, payload.key, exclude_id=question.id)
        question.key = payload.key
    if "type" in fields and payload.type is not None:
        if payload.type != question.type and question.annotations:
            raise ApiError(
                422,
                "VALIDATION_ERROR",
                "Cannot change question type while annotations exist",
            )
        question.type = payload.type
    if "criteria" in fields:
        criteria = payload.criteria
    elif "type" in fields:
        criteria = None
    else:
        criteria = question.criteria
    question.criteria = validate_question_fields(question.type, criteria)
    if payload.instructions is not None:
        question.instructions = payload.instructions
    if payload.order is not None:
        question.order = payload.order
    db.commit()
    db.refresh(question)
    return question


@router.delete("/projects/{project_id}/questions/{question_id}", response_model=Message)
def delete_question(
    question: Question = Depends(question_or_404),
    db: Session = Depends(get_db),
) -> Message:
    db.delete(question)
    db.commit()
    return Message(message="Question deleted")
