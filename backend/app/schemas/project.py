from __future__ import annotations

from datetime import datetime

from pydantic import Field, field_validator

from app.schemas.common import APIModel


class ProjectCreate(APIModel):
    name: str = Field(min_length=1, max_length=200)
    domain: str = ""
    languages: list[str] = Field(default_factory=lambda: ["zh", "en"])

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Project name is required")
        return value

    @field_validator("languages")
    @classmethod
    def normalize_languages(cls, value: list[str]) -> list[str]:
        normalized = [item.strip().lower() for item in value if item.strip()]
        return list(dict.fromkeys(normalized)) or ["en"]


class ProjectUpdate(APIModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    domain: str | None = None
    languages: list[str] | None = None

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Project name is required")
        return value

    @field_validator("languages")
    @classmethod
    def normalize_languages(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        normalized = [item.strip().lower() for item in value if item.strip()]
        return list(dict.fromkeys(normalized)) or ["en"]


class ProjectOut(APIModel):
    id: str
    name: str
    domain: str
    languages: list[str]
    question_count: int = 0
    seed_count: int = 0
    sample_count: int = 0
    pending_count: int = 0
    snapshot_count: int = 0
    created_at: datetime
    updated_at: datetime
