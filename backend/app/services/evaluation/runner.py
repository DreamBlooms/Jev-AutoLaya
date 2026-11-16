from __future__ import annotations

import json
import logging
import os
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.errors import ApiError
from app.models import DatasetSnapshot, EvaluationRun, ModelArtifact, Project
from app.schemas.jobs import EvaluationRequest
from app.services.evaluation.metrics import aggregate, markdown_report
from app.services.job_worker import wake_job_worker
from app.services.teachers.jev import JevTeacher

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(UTC)


def _latest_artifact(db: Session, project_id: str, kind: str) -> ModelArtifact | None:
    return db.scalar(
        select(ModelArtifact)
        .where(ModelArtifact.project_id == project_id, ModelArtifact.kind == kind)
        .order_by(ModelArtifact.created_at.desc())
    )


def _artifact_metadata(artifact: ModelArtifact) -> dict[str, Any]:
    return {
        "id": artifact.id,
        "name": artifact.name,
        "kind": artifact.kind,
        "path": artifact.path,
        "createdAt": artifact.created_at.isoformat() if artifact.created_at else None,
    }


TRAINED_ARTIFACT_KINDS = {
    "laya-fit": "calibration",
    "laya-finetuned": "checkpoint",
    "gliner-finetuned": "gliner_checkpoint",
}


def create_evaluation_run(
    db: Session,
    project: Project,
    payload: EvaluationRequest,
) -> EvaluationRun:
    settings = get_settings()
    snapshot = db.get(DatasetSnapshot, payload.snapshot_id)
    if snapshot is None or snapshot.project_id != project.id:
        raise ApiError(404, "NOT_FOUND", "Dataset snapshot not found for this project")
    if not payload.models:
        raise ApiError(422, "VALIDATION_ERROR", "Choose at least one model")
    allowed = {
        "jev",
        "laya-base",
        "laya-multi-base",
        "laya-fit",
        "laya-finetuned",
        "gliner-base",
        "gliner-multi-base",
        "gliner-finetuned",
    }
    unknown = [model for model in payload.models if model not in allowed]
    if unknown:
        raise ApiError(422, "VALIDATION_ERROR", f"Unsupported evaluation models: {unknown}")
    for model_key, artifact_id in payload.artifact_ids.items():
        if model_key not in TRAINED_ARTIFACT_KINDS:
            raise ApiError(
                422,
                "VALIDATION_ERROR",
                f"Artifact overrides are only supported for: {sorted(TRAINED_ARTIFACT_KINDS)}",
            )
        if model_key not in payload.models:
            raise ApiError(
                422,
                "VALIDATION_ERROR",
                f"Artifact override for unselected model: {model_key}",
            )
        artifact = db.get(ModelArtifact, artifact_id)
        if artifact is None or artifact.project_id != project.id:
            raise ApiError(404, "NOT_FOUND", f"Artifact not found for {model_key}")
        if artifact.kind != TRAINED_ARTIFACT_KINDS[model_key]:
            raise ApiError(
                422,
                "VALIDATION_ERROR",
                f"Artifact {artifact_id} is not a {TRAINED_ARTIFACT_KINDS[model_key]}",
            )
    if (
        any(model.startswith("laya") for model in payload.models)
        and not settings.laya_runtime_ready
    ):
        raise ApiError(
            400,
            "TRAINING_ERROR",
            "Laya runtime is not installed. Run ./deploy.sh setup-laya first.",
        )
    if "laya-fit" in payload.models and _latest_artifact(db, project.id, "calibration") is None:
        raise ApiError(400, "VALIDATION_ERROR", "No fit calibration artifact is available")
    if (
        "laya-finetuned" in payload.models
        and _latest_artifact(db, project.id, "checkpoint") is None
    ):
        raise ApiError(400, "VALIDATION_ERROR", "No fine-tuned checkpoint is available")
    gliner_models = [model for model in payload.models if model.startswith("gliner")]
    if gliner_models:
        if not settings.gliner_enabled or not settings.gliner_runtime_ready:
            raise ApiError(400, "TRAINING_ERROR", "GLiNER runtime is not enabled/installed")
        if not snapshot.gliner_path:
            raise ApiError(422, "VALIDATION_ERROR", "Snapshot has no GLiNER export")
        if (
            "gliner-finetuned" in payload.models
            and _latest_artifact(db, project.id, "gliner_checkpoint") is None
        ):
            raise ApiError(400, "VALIDATION_ERROR", "No fine-tuned GLiNER checkpoint is available")
    if "jev" in payload.models and not settings.jev_configured:
        raise ApiError(400, "TEACHER_ERROR", "Jev is not configured")
    run = EvaluationRun(
        project_id=project.id,
        snapshot_id=snapshot.id,
        models=payload.models,
        device=payload.device,
        status="pending",
        stage="queued",
        results={"requestedArtifacts": payload.artifact_ids},
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    wake_job_worker()
    return run


def _update(db: Session, run: EvaluationRun, **fields: Any) -> None:
    for key, value in fields.items():
        setattr(run, key, value)
    db.commit()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _run_laya(
    model_name: str,
    model_source: str,
    calibration: str,
    mode: str,
    backbone: str,
    rows_path: Path,
    output_path: Path,
    device: str,
    log_path: Path,
) -> list[dict[str, Any]]:
    settings = get_settings()
    script = Path(__file__).with_name("laya_predict.py")
    command = [
        settings.resolved_laya_python,
        str(script),
        "--data",
        str(rows_path),
        "--out",
        str(output_path),
        "--model",
        model_source,
        "--device",
        device,
        "--mode",
        mode,
    ]
    if calibration:
        command.extend(["--calibration", calibration])
    if backbone:
        command.extend(["--backbone", backbone])
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["TOKENIZERS_PARALLELISM"] = "false"
    if settings.hf_endpoint:
        env["HF_ENDPOINT"] = settings.hf_endpoint
    with log_path.open("w", encoding="utf-8") as log:
        log.write("$ " + " ".join(command) + "\n")
        log.flush()
        process = subprocess.run(
            command,
            cwd=rows_path.parent,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
            check=False,
        )
    if process.returncode != 0:
        raise RuntimeError(f"{model_name} exited with code {process.returncode}")
    return _read_jsonl(output_path)


def _run_gliner(
    model_name: str,
    model_source: str,
    rows_path: Path,
    output_path: Path,
    device: str,
    log_path: Path,
) -> list[dict[str, Any]]:
    settings = get_settings()
    script = Path(__file__).with_name("gliner_predict.py")
    command = [
        settings.resolved_gliner_python,
        str(script),
        "--data",
        str(rows_path),
        "--out",
        str(output_path),
        "--model",
        model_source,
        "--device",
        device,
    ]
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["TOKENIZERS_PARALLELISM"] = "false"
    if device == "cpu":
        env["CUDA_VISIBLE_DEVICES"] = ""
    if settings.hf_endpoint:
        env["HF_ENDPOINT"] = settings.hf_endpoint
    with log_path.open("w", encoding="utf-8") as log:
        log.write("$ " + " ".join(command) + "\n")
        log.flush()
        process = subprocess.run(
            command,
            cwd=rows_path.parent,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
            check=False,
        )
    if process.returncode != 0:
        raise RuntimeError(f"{model_name} exited with code {process.returncode}")
    return _read_jsonl(output_path)


def run_evaluation(run_id: str) -> None:
    db = SessionLocal()
    try:
        run = db.get(EvaluationRun, run_id)
        if run is None:
            return
        project = db.get(Project, run.project_id)
        snapshot = db.get(DatasetSnapshot, run.snapshot_id)
        if project is None or snapshot is None:
            _update(db, run, status="failed", stage="failed", error="Project or snapshot missing")
            return
        settings = get_settings()
        rows = _read_jsonl(Path(snapshot.laya_path))
        canonical_rows = _read_jsonl(Path(snapshot.canonical_path))
        gliner_rows = _read_jsonl(Path(snapshot.gliner_path)) if snapshot.gliner_path else []
        held_out_indices = [
            index for index, row in enumerate(rows) if row.get("split") in {"validation", "test"}
        ]
        holdout = bool(held_out_indices)
        selected_indices = held_out_indices or list(range(len(rows)))
        if settings.eval_max_rows > 0:
            selected_indices = selected_indices[: settings.eval_max_rows]
        selected = [rows[index] for index in selected_indices]
        selected_gliner = (
            [gliner_rows[index] for index in selected_indices]
            if len(gliner_rows) == len(rows)
            else []
        )
        selected_canonical = (
            [canonical_rows[index] for index in selected_indices]
            if len(canonical_rows) == len(rows)
            else selected
        )
        if not selected:
            raise ValueError("Snapshot contains no rows to evaluate")
        directory = settings.resolved_artifact_dir / project.id / "evaluations" / run.id
        directory.mkdir(parents=True, exist_ok=True)
        rows_path = directory / "evaluation.jsonl"
        _write_jsonl(rows_path, selected)
        _update(
            db,
            run,
            status="running",
            stage="preparing",
            started_at=_now(),
            progress=2,
        )

        requested_artifacts = dict((run.results or {}).get("requestedArtifacts") or {})

        def select_artifact(model_key: str) -> ModelArtifact | None:
            artifact_id = requested_artifacts.get(model_key)
            if not artifact_id:
                return _latest_artifact(db, project.id, TRAINED_ARTIFACT_KINDS[model_key])
            artifact = db.get(ModelArtifact, artifact_id)
            if (
                artifact is None
                or artifact.project_id != project.id
                or artifact.kind != TRAINED_ARTIFACT_KINDS[model_key]
            ):
                raise RuntimeError(f"Requested artifact for {model_key} is unavailable")
            return artifact

        artifacts = {
            "laya-fit": select_artifact("laya-fit"),
            "laya-finetuned": select_artifact("laya-finetuned"),
            "gliner-finetuned": select_artifact("gliner-finetuned"),
        }
        gliner_path = directory / "gliner_evaluation.jsonl"
        if selected_gliner:
            _write_jsonl(gliner_path, selected_gliner)
        teacher = JevTeacher() if "jev" in run.models else None
        results: dict[str, Any] = {
            "holdout": holdout,
            "source": "validation/test split" if holdout else "all rows (no held-out split)",
            "rows": len(selected),
            "models": {},
            "modelInfo": {},
        }
        for index, model in enumerate(run.models):
            db.refresh(run)
            if run.cancel_requested:
                _update(db, run, status="cancelled", stage="cancelled", finished_at=_now())
                return
            _update(
                db,
                run,
                stage=model,
                progress=5 + int(index / max(1, len(run.models)) * 85),
            )
            if model == "jev":
                results["modelInfo"][model] = {
                    "role": "remote",
                    "target": "jev",
                    "source": settings.resolved_jev_model,
                    "provider": settings.resolved_jev_provider,
                }
                predictions = _predict_jev(
                    teacher,
                    selected,
                    db,
                    run,
                )
            elif model.startswith("gliner"):
                if not selected_gliner:
                    raise RuntimeError("GLiNER rows do not align with this snapshot")
                if model == "gliner-base":
                    source = settings.gliner_base_model
                    results["modelInfo"][model] = {
                        "role": "base",
                        "target": "gliner",
                        "source": source,
                    }
                elif model == "gliner-multi-base":
                    source = settings.gliner_multi_model
                    results["modelInfo"][model] = {
                        "role": "base",
                        "target": "gliner",
                        "source": source,
                    }
                else:
                    artifact = artifacts["gliner-finetuned"]
                    assert artifact is not None
                    source = artifact.path
                    results["modelInfo"][model] = {
                        "role": "finetuned",
                        "target": "gliner",
                        "source": source,
                        "artifact": _artifact_metadata(artifact),
                    }
                predictions = _run_gliner(
                    model,
                    source,
                    gliner_path,
                    directory / f"{model}.jsonl",
                    "cuda" if run.device == "rocm" else run.device,
                    directory / f"{model}.log",
                )
                selected = selected_canonical
            else:
                if model == "laya-base":
                    source = settings.laya_base_model
                    calibration = ""
                    mode = "base"
                    backbone = ""
                    results["modelInfo"][model] = {
                        "role": "base",
                        "target": "laya",
                        "source": source,
                    }
                elif model == "laya-multi-base":
                    source = settings.laya_multi_model
                    calibration = ""
                    mode = "base"
                    backbone = ""
                    results["modelInfo"][model] = {
                        "role": "base",
                        "target": "laya",
                        "source": source,
                    }
                elif model == "laya-fit":
                    artifact = artifacts["laya-fit"]
                    assert artifact is not None
                    source = str(artifact.config.get("base_model") or "nandakishorm/vega-U")
                    calibration = artifact.path
                    mode = "fit"
                    backbone = str(artifact.config.get("backbone") or "")
                    results["modelInfo"][model] = {
                        "role": "fit",
                        "target": "laya",
                        "source": source,
                        "artifact": _artifact_metadata(artifact),
                    }
                else:
                    artifact = artifacts["laya-finetuned"]
                    assert artifact is not None
                    source = artifact.path
                    calibration = ""
                    mode = "checkpoint"
                    backbone = ""
                    results["modelInfo"][model] = {
                        "role": "finetuned",
                        "target": "laya",
                        "source": source,
                        "artifact": _artifact_metadata(artifact),
                    }
                predictions = _run_laya(
                    model,
                    source,
                    calibration,
                    mode,
                    backbone,
                    rows_path,
                    directory / f"{model}.jsonl",
                    "cuda" if run.device == "rocm" else run.device,
                    directory / f"{model}.log",
                )
            results["models"][model] = aggregate(
                selected,
                predictions,
                probabilities_reliable=not model.startswith("gliner"),
            )
            _update(db, run, results=results, progress=10 + int((index + 1) / len(run.models) * 85))

        report_path = directory / "report.json"
        report_path.write_text(
            json.dumps(results, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (directory / "report.md").write_text(
            markdown_report(
                {
                    "id": run.id,
                    "snapshot_id": run.snapshot_id,
                    "models": results["models"],
                    "model_info": results["modelInfo"],
                }
            ),
            encoding="utf-8",
        )
        _update(
            db,
            run,
            status="completed",
            stage="completed",
            progress=100,
            results=results,
            report_path=str(report_path),
            finished_at=_now(),
        )
    except Exception as exc:
        logger.exception("Evaluation run failed")
        run = db.get(EvaluationRun, run_id)
        if run is not None:
            _update(db, run, status="failed", stage="failed", error=str(exc), finished_at=_now())
    finally:
        db.close()


def _predict_jev(
    teacher: JevTeacher | None,
    rows: list[dict[str, Any]],
    db: Session,
    run: EvaluationRun,
) -> list[dict[str, Any]]:
    if teacher is None:
        raise RuntimeError("Jev teacher is not configured")
    from app.models import Question

    predictions = []
    for index, row in enumerate(rows):
        db.refresh(run)
        if run.cancel_requested:
            raise RuntimeError("Cancelled")
        started = time.perf_counter()
        answers: dict[str, Any] = {}
        error = None
        try:
            questions = []
            for key, question in (row.get("questions") or {}).items():
                questions.append(
                    Question(
                        key=key,
                        type=question.get("type"),
                        instructions=question.get("instructions", ""),
                        criteria=question.get("criteria"),
                    )
                )
            labels = teacher.label(row["state"], questions)
            answers = {key: label["answer"] for key, label in labels.items()}
        except Exception as exc:
            error = str(exc)
        predictions.append(
            {
                "index": index,
                "id": row.get("id"),
                "answers": answers,
                "elapsed_ms": (time.perf_counter() - started) * 1000.0,
                "error": error,
            }
        )
        if index % 5 == 0:
            _update(db, run, progress=min(90, 10 + int(index / max(1, len(rows)) * 75)))
    return predictions
