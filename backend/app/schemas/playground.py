from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, field_validator

from app.schemas.common import APIModel


class PlaygroundQuestion(APIModel):
    key: str = Field(min_length=1, max_length=100)
    type: Literal["choice", "noul", "score"]
    instructions: str = ""
    criteria: dict[str, str] | list[str] | None = None


class PlaygroundRequest(APIModel):
    project_id: str | None = None
    model: Literal[
        "laya-base",
        "laya-multi-base",
        "laya-fit",
        "laya-finetuned",
        "gliner-base",
        "gliner-multi-base",
        "gliner-finetuned",
    ] = "laya-base"
    state: Any
    questions: list[PlaygroundQuestion] = Field(default_factory=list)
    artifact_id: str | None = None
    device: Literal["auto", "cpu", "cuda", "mps", "rocm"] = "auto"

    @field_validator("state")
    @classmethod
    def check_state(cls, value: Any) -> Any:
        if not isinstance(value, (str, dict, list)):
            raise ValueError("State must be a string, object, or array")
        if value == "" or (isinstance(value, (dict, list)) and not value):
            raise ValueError("State cannot be empty")
        return value


class PlaygroundResult(APIModel):
    model: str
    model_info: dict[str, Any] = Field(default_factory=dict)
    answers: dict[str, Any] = Field(default_factory=dict)
    latency_ms: float | None = None
    routing: dict[str, Any] | None = None
    usage: dict[str, Any] | None = None
