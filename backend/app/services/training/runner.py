from __future__ import annotations

import contextlib
import json
import logging
import os
import re
import signal
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.errors import ApiError
from app.models import DatasetSnapshot, ModelArtifact, Project, TrainingJob
from app.schemas.jobs import TrainingRequest
from app.services.job_worker import wake_job_worker

logger = logging.getLogger(__name__)
EPOCH_RE = re.compile(r"epoch\s+(\d+)\s*/\s*(\d+)", re.IGNORECASE)


def _now() -> datetime:
    return datetime.now(UTC)


def create_training_job(
    db: Session,
    project: Project,
    payload: TrainingRequest,
) -> TrainingJob:
    settings = get_settings()
    snapshot = db.get(DatasetSnapshot, payload.snapshot_id)
    if snapshot is None or snapshot.project_id != project.id:
        raise ApiError(404, "NOT_FOUND", "Dataset snapshot not found for this project")
    if payload.target == "gliner":
        if not settings.gliner_enabled:
            raise ApiError(
                422,
                "RESERVED_TARGET",
                "GLiNER is disabled. Set GLINER_ENABLED=true after installing the runtime.",
            )
        if payload.mode != "finetune":
            raise ApiError(422, "VALIDATION_ERROR", "GLiNER supports fine-tune mode only")
        if not settings.gliner_runtime_ready:
            raise ApiError(
                400,
                "TRAINING_ERROR",
                "GLiNER runtime is not installed. Run ./deploy.sh setup-gliner first.",
            )
        if not snapshot.gliner_path:
            raise ApiError(422, "VALIDATION_ERROR", "Snapshot has no GLiNER export")
    else:
        if not settings.laya_runtime_ready:
            raise ApiError(
                400,
                "TRAINING_ERROR",
                "Laya runtime is not installed. Run ./deploy.sh setup-laya first.",
            )
        if payload.mode == "finetune" and not settings.resolved_laya_train_bin:
            raise ApiError(
                400,
                "TRAINING_ERROR",
                "laya-train was not found in the Laya venv. Run ./deploy.sh setup-laya.",
            )
    job = TrainingJob(
        project_id=project.id,
        snapshot_id=snapshot.id,
        target=payload.target,
        mode=payload.mode,
        device=payload.device,
        config=payload.model_dump(),
        status="pending",
        stage="queued",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    wake_job_worker()
    return job


def _update(db: Session, job: TrainingJob, **fields: Any) -> None:
    for key, value in fields.items():
        setattr(job, key, value)
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


def _prepare_dataset(snapshot: DatasetSnapshot, directory: Path) -> tuple[Path, Path | None]:
    rows = _read_jsonl(Path(snapshot.laya_path))
    if not rows:
        raise ValueError("Snapshot contains no Laya rows")
    train = [row for row in rows if row.get("split", "train") == "train"]
    held_out = [row for row in rows if row.get("split") in {"validation", "test"}]
    if not train:
        train = rows
        held_out = []
    train_path = directory / "train.jsonl"
    eval_path = directory / "eval.jsonl" if held_out else None
    _write_jsonl(train_path, train)
    if eval_path is not None:
        _write_jsonl(eval_path, held_out)
    return train_path, eval_path


def _prepare_gliner_dataset(snapshot: DatasetSnapshot, directory: Path) -> tuple[Path, Path | None]:
    rows = _read_jsonl(Path(snapshot.gliner_path or ""))
    if not rows:
        raise ValueError("Snapshot contains no GLiNER rows")
    train = [row for row in rows if (row.get("meta") or {}).get("split", "train") == "train"]
    held_out = [
        row for row in rows if (row.get("meta") or {}).get("split") in {"validation", "test"}
    ]
    if not train:
        train = rows
        held_out = []
    train_path = directory / "gliner_train.jsonl"
    eval_path = directory / "gliner_eval.jsonl" if held_out else None
    _write_jsonl(train_path, train)
    if eval_path is not None:
        _write_jsonl(eval_path, held_out)
    return train_path, eval_path


def _gliner_command(
    payload: TrainingRequest,
    train_path: Path,
    eval_path: Path | None,
    output_dir: Path,
) -> list[str]:
    settings = get_settings()
    config = payload.config
    script = Path(__file__).with_name("gliner_train.py")
    command = [
        settings.resolved_gliner_python,
        str(script),
        "--data",
        str(train_path),
        "--out",
        str(output_dir),
        "--base",
        payload.base_model or settings.gliner_base_model,
        "--epochs",
        str(config.epochs),
        "--batch-size",
        str(config.micro_batch),
        "--grad-accum",
        str(config.grad_accum),
        "--encoder-lr",
        str(config.encoder_lr),
        "--task-lr",
        str(config.head_lr),
        "--device",
        "cuda" if payload.device == "rocm" else payload.device,
        "--seed",
        str(config.seed),
    ]
    if eval_path is not None:
        command.extend(["--eval", str(eval_path)])
    return command


def _finetune_command(
    payload: TrainingRequest,
    train_path: Path,
    eval_path: Path | None,
    output_dir: Path,
) -> list[str]:
    settings = get_settings()
    config = payload.config
    script = Path(__file__).with_name("laya_train_metrics.py")
    command = [
        settings.resolved_laya_python,
        str(script),
        "--data",
        str(train_path),
        "--base",
        payload.base_model or settings.laya_base_model,
        "--out",
        str(output_dir),
        "--epochs",
        str(config.epochs),
        "--micro-batch",
        str(config.micro_batch),
        "--grad-accum",
        str(config.grad_accum),
        "--encoder-lr",
        str(config.encoder_lr),
        "--head-lr",
        str(config.head_lr),
        "--loss",
        config.loss,
        "--device",
        "cuda" if payload.device == "rocm" else payload.device,
        "--seed",
        str(config.seed),
        "--label-smoothing",
        str(config.label_smoothing),
        "--target-error",
        str(config.target_error),
        "--min-abstain-n",
        str(config.min_abstain_n),
    ]
    if eval_path is not None:
        command.extend(["--eval", str(eval_path)])
    if config.shuffle_options:
        command.append("--shuffle-options")
    if config.freeze_encoder:
        command.append("--freeze-encoder")
    if config.max_len:
        command.extend(["--max-len", str(config.max_len)])
    if config.head_max_len:
        command.extend(["--head-max-len", str(config.head_max_len)])
    return command


def _fit_command(
    payload: TrainingRequest,
    train_path: Path,
    output_dir: Path,
) -> list[str]:
    settings = get_settings()
    script = Path(__file__).with_name("laya_fit.py")
    command = [
        settings.resolved_laya_python,
        str(script),
        "--data",
        str(train_path),
        "--out",
        str(output_dir),
        "--device",
        "cuda" if payload.device == "rocm" else payload.device,
    ]
    if settings.laya_fit_model:
        command.extend(["--model", settings.laya_fit_model])
    if settings.laya_fit_backbone:
        command.extend(["--backbone", settings.laya_fit_backbone])
    return command


def _terminate_group(pid: int | None) -> None:
    if not pid:
        return
    try:
        os.killpg(os.getpgid(pid), signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.kill(pid, signal.SIGTERM)


def run_training_job(job_id: str) -> None:
    db = SessionLocal()
    process: subprocess.Popen[str] | None = None
    try:
        job = db.get(TrainingJob, job_id)
        if job is None:
            return
        payload = TrainingRequest.model_validate(job.config)
        snapshot = db.get(DatasetSnapshot, job.snapshot_id)
        project = db.get(Project, job.project_id)
        if snapshot is None or project is None:
            _update(db, job, status="failed", stage="failed", error="Dataset or project missing")
            return
        settings = get_settings()
        artifact_root = settings.resolved_artifact_dir / project.id / job.id
        dataset_dir = artifact_root / "dataset"
        dataset_dir.mkdir(parents=True, exist_ok=True)
        log_path = artifact_root / "train.log"
        job.log_path = str(log_path)
        _update(db, job, status="running", stage="preparing", started_at=_now(), progress=1)

        if payload.target == "gliner":
            train_path, eval_path = _prepare_gliner_dataset(snapshot, dataset_dir)
            output_dir = artifact_root / "gliner"
        else:
            train_path, eval_path = _prepare_dataset(snapshot, dataset_dir)
            output_dir = (
                artifact_root / "checkpoint"
                if payload.mode == "finetune"
                else artifact_root / "calibration"
            )
        output_dir.mkdir(parents=True, exist_ok=True)
        if payload.target == "gliner":
            command = _gliner_command(payload, train_path, eval_path, output_dir)
        elif payload.mode == "finetune":
            command = _finetune_command(payload, train_path, eval_path, output_dir)
        else:
            command = _fit_command(payload, train_path, output_dir)
        (artifact_root / "command.json").write_text(
            json.dumps({"command": command, "cwd": str(artifact_root)}, indent=2),
            encoding="utf-8",
        )
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["TOKENIZERS_PARALLELISM"] = "false"
        if payload.device == "cpu":
            env["CUDA_VISIBLE_DEVICES"] = ""
        if settings.hf_endpoint:
            env["HF_ENDPOINT"] = settings.hf_endpoint
        _update(db, job, stage="training", progress=3)
        with log_path.open("w", encoding="utf-8") as log:
            log.write("$ " + " ".join(command) + "\n")
            log.flush()
            process = subprocess.Popen(
                command,
                cwd=artifact_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=env,
                start_new_session=True,
            )
            _update(db, job, pid=process.pid)
            assert process.stdout is not None
            for line in process.stdout:
                log.write(line)
                log.flush()
                match = EPOCH_RE.search(line)
                if match:
                    epoch = int(match.group(1))
                    total = max(1, int(match.group(2)))
                    _update(
                        db,
                        job,
                        progress=min(92, 5 + int(epoch / total * 85)),
                        stage="training",
                    )
                db.refresh(job)
                if job.cancel_requested:
                    _terminate_group(process.pid)
                    break
            returncode = process.wait()
        db.refresh(job)
        if job.cancel_requested:
            _update(
                db,
                job,
                status="cancelled",
                stage="cancelled",
                finished_at=_now(),
                error="Cancelled by user",
            )
            return
        if returncode != 0:
            _update(
                db,
                job,
                status="failed",
                stage="failed",
                progress=100,
                error=f"Training process exited with code {returncode}",
                finished_at=_now(),
            )
            return

        if payload.target == "gliner":
            report_path = output_dir / "gliner_train_report.json"
        elif payload.mode == "finetune":
            report_path = output_dir / "train_report.json"
        else:
            report_path = output_dir / "fit_report.json"
        metrics: dict[str, Any] = {}
        if report_path.exists():
            try:
                metrics = json.loads(report_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                metrics = {}
        if payload.target == "gliner":
            kind = "gliner_checkpoint"
            artifact_path = output_dir / "final"
            target = "gliner"
            base_model = payload.base_model or get_settings().gliner_base_model
            backbone = ""
        else:
            kind = "checkpoint" if payload.mode == "finetune" else "calibration"
            artifact_path = output_dir
            target = "laya"
            base_model = (
                get_settings().laya_fit_model or "nandakishorm/vega-U"
                if payload.mode == "fit"
                else payload.base_model or get_settings().laya_base_model
            )
            backbone = get_settings().laya_fit_backbone
        artifact_name = f"{project.name} · {payload.target} · {job.id[:8]}"
        if payload.mode == "fit" and metrics.get("fit_mode") == "heads_only":
            artifact_name += " (heads only)"
        artifact = ModelArtifact(
            project_id=project.id,
            training_job_id=job.id,
            target=target,
            name=artifact_name,
            kind=kind,
            path=str(artifact_path),
            metrics=metrics,
            config={
                "mode": payload.mode,
                "base_model": base_model,
                "device": payload.device,
                "backbone": backbone,
                "training_config": payload.config.model_dump(),
            },
        )
        db.add(artifact)
        _update(
            db,
            job,
            status="completed",
            stage="completed",
            progress=100,
            metrics=metrics,
            artifact_path=str(artifact_path),
            finished_at=_now(),
        )
    except Exception as exc:
        logger.exception("Training job failed")
        job = db.get(TrainingJob, job_id)
        if job is not None:
            _update(
                db,
                job,
                status="failed",
                stage="failed",
                error=str(exc),
                finished_at=_now(),
            )
    finally:
        if process is not None and process.poll() is None:
            _terminate_group(process.pid)
        db.close()
