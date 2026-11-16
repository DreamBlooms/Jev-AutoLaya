from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.schemas.common import APIModel


class DatasetSnapshotOut(APIModel):
    id: str
    project_id: str
    version: int
    canonical_path: str
    laya_path: str
    gliner_path: str | None = None
    split_counts: dict[str, int] = Field(default_factory=dict)
    label_distribution: dict[str, dict[str, int]] = Field(default_factory=dict)
    prompt_versions: dict[str, str] = Field(default_factory=dict)
    teacher_models: dict[str, int] = Field(default_factory=dict)
    created_at: datetime
    downloads: dict[str, str] = Field(default_factory=dict)
