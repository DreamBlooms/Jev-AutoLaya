from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.common import APIModel


class LLMOverride(APIModel):
    base_url: str | None = None
    model: str | None = None
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None, ge=64, le=32768)
    think_budget: int | None = Field(default=None, ge=0, le=32768)
    think_level: Literal["minimal", "low", "medium", "high"] | None = None


class GenerationRequest(APIModel):
    count: int = Field(default=50, ge=1, le=2000)
    languages: list[str] = Field(default_factory=lambda: ["en"])
    difficulty: dict[str, float] = Field(
        default_factory=lambda: {"easy": 0.5, "medium": 0.35, "hard": 0.15}
    )
    negative_ratio: float = Field(default=0.1, ge=0, le=1)
    label_balanced: bool = True
    teacher: Literal["jev", "llm", "none", "human"] = "jev"
    custom_prompt: str | None = Field(default=None, max_length=8000)
    system_prompt_template: str | None = Field(default=None, max_length=20000)
    user_prompt_template: str | None = Field(default=None, max_length=20000)
    llm: LLMOverride | None = None


class GenerationPromptDefaultsOut(APIModel):
    system: str
    user: str
    placeholders: list[str] = Field(default_factory=list)


class GenerationPreviewOut(APIModel):
    model: str
    endpoint: str
    language: str
    batch_size: int
    body: dict


class GenerationJobOut(APIModel):
    id: str
    project_id: str
    status: str
    stage: str
    progress: int
    config: dict
    target_count: int
    generated_count: int
    accepted_count: int
    rejected_count: int
    error: str | None = None
    cancel_requested: bool = False
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class TrainingConfig(APIModel):
    epochs: int = Field(default=4, ge=1, le=100)
    micro_batch: int = Field(default=8, ge=1, le=256)
    grad_accum: int = Field(default=8, ge=1, le=256)
    encoder_lr: float = Field(default=2.5e-5, gt=0)
    head_lr: float = Field(default=1e-4, gt=0)
    loss: Literal["rlcd", "soft-ce"] = "rlcd"
    label_smoothing: float = Field(default=0.0, ge=0, lt=1)
    shuffle_options: bool = False
    freeze_encoder: bool = False
    max_len: int | None = Field(default=None, ge=16, le=16384)
    head_max_len: int | None = Field(default=None, ge=16, le=4096)
    target_error: float = Field(default=0.1, ge=0, le=1)
    min_abstain_n: int = Field(default=10, ge=1)
    seed: int = 0


class TrainingRequest(APIModel):
    project_id: str
    snapshot_id: str
    target: Literal["laya", "gliner"] = "laya"
    mode: Literal["fit", "finetune"] = "finetune"
    device: Literal["auto", "cpu", "cuda", "mps", "rocm"] = "auto"
    base_model: str | None = None
    config: TrainingConfig = Field(default_factory=TrainingConfig)


class TrainingJobOut(APIModel):
    id: str
    project_id: str
    snapshot_id: str
    target: str
    mode: str
    device: str
    config: dict
    status: str
    stage: str
    progress: int
    pid: int | None = None
    metrics: dict
    artifact_path: str | None = None
    log_path: str | None = None
    error: str | None = None
    cancel_requested: bool = False
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class TrainingMetricPoint(APIModel):
    step: int | None = None
    epoch: float | None = None
    value: float


class TrainingMetricSeries(APIModel):
    key: str
    points: list[TrainingMetricPoint] = Field(default_factory=list)


class TrainingHeadOut(APIModel):
    key: str
    fitted: bool | None = None
    examples: int | None = None
    cv_accuracy: float | None = None
    engine_accuracy: float | None = None
    chance: float | None = None
    ece_before: float | None = None
    ece_after: float | None = None
    temperature: float | None = None
    used_by_auto: bool | None = None
    reason: str | None = None


class TrainingChartsOut(APIModel):
    target: str
    mode: str
    series: list[TrainingMetricSeries] = Field(default_factory=list)
    summary: dict = Field(default_factory=dict)
    heads: list[TrainingHeadOut] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    log_path: str | None = None


class EvaluationRequest(APIModel):
    project_id: str
    snapshot_id: str
    models: list[str] = Field(default_factory=lambda: ["laya-base"])
    device: Literal["auto", "cpu", "cuda", "mps", "rocm"] = "auto"
    artifact_ids: dict[str, str] = Field(default_factory=dict)


class EvaluationRunOut(APIModel):
    id: str
    project_id: str
    snapshot_id: str
    models: list[str]
    device: str
    status: str
    stage: str
    progress: int
    results: dict
    report_path: str | None = None
    error: str | None = None
    cancel_requested: bool = False
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class ModelArtifactOut(APIModel):
    id: str
    project_id: str
    training_job_id: str | None = None
    target: str
    name: str
    kind: str
    path: str
    metrics: dict
    config: dict
    created_at: datetime


class DeploymentCreate(APIModel):
    artifact_id: str
    target: Literal["laya", "gliner"] = "laya"
    host: str | None = None
    port: int | None = Field(default=None, ge=1024, le=65535)


class DeploymentOut(APIModel):
    id: str
    artifact_id: str | None = None
    target: str
    host: str
    port: int
    status: str
    pid: int | None = None
    log_path: str | None = None
    error: str | None = None
    started_at: datetime | None = None
    stopped_at: datetime | None = None
    created_at: datetime
