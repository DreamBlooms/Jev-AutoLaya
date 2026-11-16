from __future__ import annotations

import json
import shutil
import tempfile
import threading
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.errors import ApiError
from app.models import ModelArtifact, Project
from app.schemas.playground import PlaygroundRequest, PlaygroundResult
from app.services.evaluation.runner import (
    TRAINED_ARTIFACT_KINDS,
    _artifact_metadata,
    _latest_artifact,
    _run_gliner,
    _run_laya,
)

router = APIRouter(tags=["playground"])
PLAYGROUND_LOCK = threading.Lock()


def _question_spec(question: Any) -> dict[str, Any]:
    spec: dict[str, Any] = {
        "type": question.type,
        "instructions": question.instructions,
    }
    if question.type == "choice":
        spec["criteria"] = question.criteria or {}
    elif question.type in {"score", "noul"} and question.criteria:
        spec["criteria"] = question.criteria
    return spec


def _state_text(state: Any) -> str:
    if isinstance(state, str):
        return state
    if not isinstance(state, dict):
        return json.dumps(state, ensure_ascii=False)
    if set(state) == {"text"}:
        return str(state["text"])
    lines = []
    for key, value in state.items():
        rendered = (
            json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)
        )
        lines.append(f"{key}: {rendered}")
    return "\n".join(lines)


def _gliner_row(state: Any, questions: list[Any]) -> dict[str, Any]:
    classifications = []
    for question in questions:
        item: dict[str, Any] = {
            "task": question.key,
            "type": question.type,
            "prompt": question.instructions,
        }
        if question.type == "choice":
            criteria = question.criteria if isinstance(question.criteria, dict) else {}
            item["labels"] = list(criteria)
            if criteria:
                item["label_descriptions"] = criteria
        elif question.type == "noul":
            item["labels"] = ["yes", "no"]
            criteria = question.criteria if isinstance(question.criteria, dict) else {}
            descriptions = {
                label: criteria[key]
                for key, label in (("true", "yes"), ("false", "no"))
                if criteria.get(key)
            }
            if descriptions:
                item["label_descriptions"] = descriptions
        else:
            item["labels"] = (
                list(question.criteria)
                if isinstance(question.criteria, list) and question.criteria
                else [str(index) for index in range(6)]
            )
        classifications.append(item)
    return {
        "input": _state_text(state),
        "output": {"classifications": classifications},
    }


def _artifact_for(
    db: Session,
    project_id: str,
    model: str,
    artifact_id: str | None,
) -> ModelArtifact | None:
    kind = TRAINED_ARTIFACT_KINDS[model]
    if not artifact_id:
        return _latest_artifact(db, project_id, kind)
    artifact = db.get(ModelArtifact, artifact_id)
    if artifact is None or artifact.project_id != project_id:
        raise ApiError(404, "NOT_FOUND", "Artifact not found for this project")
    if artifact.kind != kind:
        raise ApiError(422, "VALIDATION_ERROR", f"Artifact is not a {kind}")
    return artifact


def _tail(path: Path, limit: int = 2000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[-limit:]
    except OSError:
        return ""


@router.post("/playground/run", response_model=PlaygroundResult)
def run_playground(
    payload: PlaygroundRequest,
    db: Session = Depends(get_db),
) -> PlaygroundResult:
    project = None
    if payload.project_id:
        project = db.get(Project, payload.project_id)
        if project is None:
            raise ApiError(404, "NOT_FOUND", "Project not found")
    trained_model = payload.model in TRAINED_ARTIFACT_KINDS
    if trained_model and project is None:
        raise ApiError(422, "VALIDATION_ERROR", "Select a project to test a trained artifact")

    questions: list[Any] = list(payload.questions)
    if not questions and project is not None:
        questions = list(project.questions)
    if not questions:
        raise ApiError(422, "VALIDATION_ERROR", "Add at least one question before using Playground")
    keys = [question.key for question in questions]
    if len(keys) != len(set(keys)):
        raise ApiError(422, "VALIDATION_ERROR", "Question keys must be unique")
    for question in questions:
        if question.type == "choice" and not (
            isinstance(question.criteria, dict) and question.criteria
        ):
            raise ApiError(422, "VALIDATION_ERROR", f"Choice question {question.key} needs options")
        if question.type == "score" and not (
            isinstance(question.criteria, list) and question.criteria
        ):
            raise ApiError(422, "VALIDATION_ERROR", f"Score question {question.key} needs labels")

    settings = get_settings()
    target = "gliner" if payload.model.startswith("gliner") else "laya"
    if target == "laya" and not settings.laya_runtime_ready:
        raise ApiError(400, "TRAINING_ERROR", "Laya runtime is not installed")
    if target == "gliner" and (not settings.gliner_enabled or not settings.gliner_runtime_ready):
        raise ApiError(400, "TRAINING_ERROR", "GLiNER runtime is not enabled or installed")

    artifact: ModelArtifact | None = None
    source = ""
    calibration = ""
    mode = "base"
    backbone = ""
    info: dict[str, Any] = {"target": target}
    if payload.model in TRAINED_ARTIFACT_KINDS:
        assert project is not None
        artifact = _artifact_for(db, project.id, payload.model, payload.artifact_id)
        if artifact is None:
            raise ApiError(400, "VALIDATION_ERROR", "No artifact of this kind is available")
        info.update(
            {
                "role": "fit" if payload.model == "laya-fit" else "finetuned",
                "artifact": _artifact_metadata(artifact),
            }
        )
        if payload.model == "laya-fit":
            source = str(
                artifact.config.get("base_model")
                or settings.laya_fit_model
                or "nandakishorm/vega-U"
            )
            calibration = artifact.path
            mode = "fit"
            backbone = str(artifact.config.get("backbone") or settings.laya_fit_backbone)
        else:
            source = artifact.path
            mode = "checkpoint" if target == "laya" else "base"
        info["source"] = source
    else:
        info["role"] = "base"
        if payload.model == "laya-multi-base":
            source = settings.laya_multi_model
        elif payload.model == "laya-base":
            source = settings.laya_base_model
        elif payload.model == "gliner-multi-base":
            source = settings.gliner_multi_model
        else:
            source = settings.gliner_base_model
        info["source"] = source

    playground_root = settings.resolved_artifact_dir / ".playground"
    playground_root.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="run-", dir=playground_root))
    rows_path = directory / "input.jsonl"
    output_path = directory / "output.jsonl"
    log_path = directory / "run.log"
    if target == "laya":
        row = {
            "state": payload.state,
            "questions": {question.key: _question_spec(question) for question in questions},
        }
    else:
        row = _gliner_row(payload.state, questions)
    rows_path.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")

    try:
        with PLAYGROUND_LOCK:
            if target == "laya":
                predictions = _run_laya(
                    payload.model,
                    source,
                    calibration,
                    mode,
                    backbone,
                    rows_path,
                    output_path,
                    "cuda" if payload.device == "rocm" else payload.device,
                    log_path,
                )
            else:
                predictions = _run_gliner(
                    payload.model,
                    source,
                    rows_path,
                    output_path,
                    "cuda" if payload.device == "rocm" else payload.device,
                    log_path,
                )
        if not predictions:
            raise ApiError(500, "PLAYGROUND_ERROR", "Model returned no prediction")
        prediction = predictions[0]
        if prediction.get("error"):
            raise ApiError(500, "PLAYGROUND_ERROR", str(prediction["error"]))
        return PlaygroundResult(
            model=payload.model,
            model_info=info,
            answers=prediction.get("answers") or {},
            latency_ms=prediction.get("elapsed_ms"),
            routing=prediction.get("routing"),
            usage=prediction.get("usage"),
        )
    except ApiError:
        raise
    except Exception as exc:
        raise ApiError(
            500,
            "PLAYGROUND_ERROR",
            f"{exc}\n{_tail(log_path)}".strip(),
        ) from exc
    finally:
        shutil.rmtree(directory, ignore_errors=True)
