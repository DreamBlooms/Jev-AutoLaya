from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field, field_validator

from app.schemas.common import APIModel


class SeedCreate(APIModel):
    state: dict[str, Any]
    labels: dict[str, Any] = Field(default_factory=dict)
    source: str = "manual"
    language: str = "en"

    @field_validator("state")
    @classmethod
    def check_state(cls, value: dict[str, Any]) -> dict[str, Any]:
        if not value:
            raise ValueError("Seed state cannot be empty")
        return value


class SeedImport(APIModel):
    samples: list[SeedCreate] = Field(min_length=1)


class SeedPromoteRequest(APIModel):
    seed_ids: list[str] = Field(default_factory=list)


class SeedOut(APIModel):
    id: str
    project_id: str
    state: dict[str, Any]
    labels: dict[str, Any]
    source: str
    language: str
    created_at: datetime


class SeedImportResult(APIModel):
    imported: int
    seeds: list[SeedOut] = Field(default_factory=list)
