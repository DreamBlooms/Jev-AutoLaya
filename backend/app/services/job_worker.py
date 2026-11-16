from __future__ import annotations

import contextlib
import logging
import os
import signal
import threading
import time
from datetime import UTC, datetime

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models import EvaluationRun, GenerationJob, TrainingJob

logger = logging.getLogger(__name__)
_event = threading.Event()
_threads: dict[str, threading.Thread] = {}
_lock = threading.Lock()
TERMINAL = {"completed", "failed", "cancelled"}


def _now() -> datetime:
    return datetime.now(UTC)


def wake_job_worker() -> None:
    _event.set()


def _recover_interrupted() -> None:
    db = SessionLocal()
    try:
        now = _now()
        for job in db.scalars(select(TrainingJob).where(TrainingJob.status == "running")):
            if job.pid:
                try:
                    os.killpg(os.getpgid(job.pid), signal.SIGTERM)
                except (ProcessLookupError, PermissionError):
                    with contextlib.suppress(ProcessLookupError, PermissionError):
                        os.kill(job.pid, signal.SIGTERM)
            job.status = "failed"
            job.stage = "failed"
            job.error = "Interrupted by AutoLaya restart"
            job.finished_at = now
        for model in (GenerationJob, EvaluationRun):
            for job in db.scalars(select(model).where(model.status == "running")):
                job.status = "failed"
                job.stage = "failed"
                job.error = "Interrupted by AutoLaya restart"
                job.finished_at = now
        db.commit()
    finally:
        db.close()


MODELS = {
    "generation": GenerationJob,
    "training": TrainingJob,
    "evaluation": EvaluationRun,
}


def _next_job(kind: str) -> str | None:
    db = SessionLocal()
    try:
        model = MODELS[kind]
        job = db.scalar(
            select(model).where(model.status == "pending").order_by(model.created_at).limit(1)
        )
        return job.id if job is not None else None
    finally:
        db.close()


def _loop(kind: str) -> None:
    while True:
        try:
            job_id = _next_job(kind)
            if job_id is None:
                _event.wait(0.5)
                _event.clear()
                continue
            logger.info("Starting %s job %s", kind, job_id)
            if kind == "generation":
                from app.services.generation.runner import run_generation_job

                run_generation_job(job_id)
            elif kind == "training":
                from app.services.training.runner import run_training_job

                run_training_job(job_id)
            else:
                from app.services.evaluation.runner import run_evaluation

                run_evaluation(job_id)
            logger.info("Finished %s job %s", kind, job_id)
        except Exception:
            logger.exception("%s worker failed", kind)
            time.sleep(1)
        _event.set()


def start_job_worker() -> None:
    settings = get_settings()
    if not settings.job_worker_enabled:
        return
    with _lock:
        if any(thread.is_alive() for thread in _threads.values()):
            return
        _recover_interrupted()
        for kind in MODELS:
            thread = threading.Thread(
                target=_loop,
                args=(kind,),
                name=f"autolaya-{kind}-worker",
                daemon=True,
            )
            _threads[kind] = thread
            thread.start()
        logger.info("Job workers started")
