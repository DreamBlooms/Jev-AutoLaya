from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field, field_validator, model_validator

from app.schemas.common import APIModel
from app.services.questions import validate_key, validate_question_fields


class QuestionCreate(APIModel):
    key: str = Field(min_length=1, max_length=64)
    type: str
    instructions: str = ""
    criteria: Any | None = None
    order: int = 0

    @field_validator("key")
    @classmethod
    def check_key(cls, value: str) -> str:
        return validate_key(value)

    @model_validator(mode="after")
    def check_question(self) -> QuestionCreate:
        self.criteria = validate_question_fields(self.type, self.criteria)
        return self


class QuestionUpdate(APIModel):
    key: str | None = Field(default=None, min_length=1, max_length=64)
    type: str | None = None
    instructions: str | None = None
    criteria: Any | None = None
    order: int | None = None

    @field_validator("key")
    @classmethod
    def check_key(cls, value: str | None) -> str | None:
        return validate_key(value) if value is not None else None


class QuestionOut(APIModel):
    id: str
    project_id: str
    key: str
    type: str
    instructions: str
    criteria: Any | None
    order: int
    created_at: datetime
    updated_at: datetime
