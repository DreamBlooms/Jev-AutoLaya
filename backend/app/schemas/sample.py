from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field, field_validator

from app.schemas.common import APIModel
from app.schemas.question import QuestionOut


class SampleCreate(APIModel):
    state: dict[str, Any]
    meta: dict[str, Any] = Field(default_factory=dict)
    labels: dict[str, Any] = Field(default_factory=dict)
    source: str = "manual"
    language: str = "en"
    difficulty: str = "medium"

    @field_validator("state")
    @classmethod
    def check_state(cls, value: dict[str, Any]) -> dict[str, Any]:
        if not value:
            raise ValueError("Sample state cannot be empty")
        return value


class AnnotationOut(APIModel):
    id: str
    question_id: str
    question_key: str
    question_type: str
    answer: dict[str, Any]
    teacher: str
    teacher_model: str | None = None
    confidence: float | None = None
    probabilities: dict[str, float] | None = None
    status: str
    reviewer: str | None = None
    review_note: str | None = None
    created_at: datetime
    updated_at: datetime


class SampleOut(APIModel):
    id: str
    project_id: str
    state: dict[str, Any]
    meta: dict[str, Any]
    source: str
    generation_job_id: str | None = None
    language: str
    difficulty: str
    status: str
    annotation_count: int = 0
    created_at: datetime
    updated_at: datetime


class SampleDetail(SampleOut):
    annotations: list[AnnotationOut] = Field(default_factory=list)
    questions: list[QuestionOut] = Field(default_factory=list)
    missing_question_ids: list[str] = Field(default_factory=list)


class SampleImportResult(APIModel):
    imported: int
    heldout: int
    samples: list[SampleOut] = Field(default_factory=list)


class AnswerUpdate(APIModel):
    answer: Any
    reviewer: str = "human"
    review_note: str | None = None


class RejectRequest(APIModel):
    reviewer: str = "human"
    review_note: str | None = None


class AcceptRequest(APIModel):
    reviewer: str = "human"
    review_note: str | None = None
