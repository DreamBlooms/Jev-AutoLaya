from __future__ import annotations

import json
import logging
import math
import random
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.errors import ApiError
from app.models import Annotation, GenerationJob, Project, Question, Sample, SeedSample
from app.schemas.jobs import GenerationRequest
from app.services.answers import normalize_answer
from app.services.generation.parser import parse_states
from app.services.generation.prompts import (
    PromptTemplateError,
    build_messages,
    validate_prompt_templates,
)
from app.services.job_worker import wake_job_worker
from app.services.llm.openai_compat import LLMError, OpenAICompatibleClient
from app.services.teachers.jev import JevTeacher

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(UTC)


def _labels_from_llm(
    questions: list[Question],
    raw_labels: dict[str, Any],
    model: str,
) -> dict[str, dict[str, Any]]:
    labels: dict[str, dict[str, Any]] = {}
    missing = []
    for question in questions:
        if question.key not in raw_labels:
            missing.append(question.key)
            continue
        answer = normalize_answer(question, raw_labels[question.key])
        labels[question.key] = {
            "answer": answer,
            "teacher": "llm",
            "teacher_model": model,
            "confidence": answer.get("confidence"),
            "probabilities": answer.get("probabilities"),
        }
    if missing:
        raise ValueError(f"LLM omitted labels for: {', '.join(missing)}")
    return labels


def _wait_if_paused(db: Session, job: GenerationJob) -> bool:
    while True:
        db.refresh(job)
        if job.cancel_requested:
            _update(
                db,
                job,
                status="cancelled",
                stage="cancelled",
                finished_at=_now(),
            )
            return False
        if job.status != "paused":
            return True
        time.sleep(1)


def _weighted_difficulty(distribution: dict[str, float]) -> str:
    values = {key: max(0.0, float(value)) for key, value in distribution.items()}
    total = sum(values.values())
    if total <= 0:
        return "medium"
    return random.choices(list(values), weights=list(values.values()), k=1)[0]


def create_generation_job(
    db: Session,
    project: Project,
    payload: GenerationRequest,
) -> GenerationJob:
    settings = get_settings()
    if not project.questions:
        raise ApiError(422, "VALIDATION_ERROR", "Add at least one question before generating")
    if not settings.llm_api_key:
        raise ApiError(400, "LLM_ERROR", "LLM_API_KEY is not configured in backend/.env")
    if payload.teacher == "jev" and not settings.jev_configured:
        raise ApiError(
            400,
            "TEACHER_ERROR",
            "Jev is not configured. Set TYPESAFE_API_KEY or OPENROUTER_API_KEY, "
            "or choose teacher=none.",
        )
    try:
        validate_prompt_templates(
            payload.system_prompt_template,
            payload.user_prompt_template,
        )
    except PromptTemplateError as exc:
        raise ApiError(422, "VALIDATION_ERROR", str(exc)) from exc
    job = GenerationJob(
        project_id=project.id,
        status="pending",
        stage="queued",
        target_count=payload.count,
        config=payload.model_dump(),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    wake_job_worker()
    return job


def _update(db: Session, job: GenerationJob, **fields: Any) -> None:
    for key, value in fields.items():
        setattr(job, key, value)
    db.commit()


def run_generation_job(job_id: str) -> None:
    db = SessionLocal()
    client: OpenAICompatibleClient | None = None
    try:
        job = db.get(GenerationJob, job_id)
        if job is None:
            return
        project = db.get(Project, job.project_id)
        if project is None:
            _update(
                db,
                job,
                status="failed",
                stage="failed",
                error="Project not found",
                finished_at=_now(),
            )
            return
        questions = list(
            db.scalars(
                select(Question).where(Question.project_id == project.id).order_by(Question.order)
            )
        )
        seeds = list(db.scalars(select(SeedSample).where(SeedSample.project_id == project.id)))
        config = GenerationRequest.model_validate(job.config)
        _update(
            db,
            job,
            status="running",
            stage="generating",
            started_at=_now(),
            error=None,
        )

        teacher = JevTeacher() if config.teacher == "jev" else None

        llm_override = config.llm or None
        client = OpenAICompatibleClient(
            base_url=llm_override.base_url if llm_override else None,
            model=llm_override.model if llm_override else None,
            temperature=llm_override.temperature if llm_override else None,
            max_tokens=llm_override.max_tokens if llm_override else None,
            think_budget=llm_override.think_budget if llm_override else None,
            think_level=llm_override.think_level if llm_override else None,
        )
        settings = get_settings()
        languages = [language for language in config.languages if language] or ["en"]
        languages = list(dict.fromkeys(languages))
        allocation = _allocate(config.count, languages)
        seen: set[str] = set()
        generated = 0
        accepted = 0
        rejected = 0
        last_error: str | None = None

        for language in languages:
            language_target = allocation[language]
            language_generated = 0
            attempts = 0
            max_attempts = max(
                settings.generation_max_attempts,
                math.ceil(language_target / max(1, settings.generation_batch_size)) + 2,
            )
            while language_generated < language_target and attempts < max_attempts:
                db.refresh(job)
                if job.cancel_requested:
                    _update(
                        db,
                        job,
                        status="cancelled",
                        stage="cancelled",
                        finished_at=_now(),
                    )
                    return
                attempts += 1
                batch_size = min(
                    settings.generation_batch_size,
                    language_target - language_generated,
                )
                messages = build_messages(
                    project=project,
                    questions=questions,
                    seeds=seeds,
                    count=batch_size,
                    language=language,
                    difficulty=config.difficulty,
                    negative_ratio=config.negative_ratio,
                    label_balanced=config.label_balanced,
                    label_with_llm=config.teacher == "llm",
                    custom_prompt=config.custom_prompt,
                    system_prompt_template=config.system_prompt_template,
                    user_prompt_template=config.user_prompt_template,
                )
                try:
                    payload = client.chat_json(messages)
                    states = parse_states(
                        payload,
                        language=language,
                        default_difficulty=_weighted_difficulty(config.difficulty),
                    )
                except LLMError as exc:
                    last_error = str(exc)
                    logger.warning("Generation batch failed: %s", exc)
                    continue
                if not states:
                    last_error = "LLM returned no usable states"
                    continue

                candidates = []
                for item in states:
                    if language_generated + len(candidates) >= language_target:
                        break
                    fingerprint = json.dumps(item["state"], ensure_ascii=False, sort_keys=True)
                    if fingerprint in seen:
                        rejected += 1
                        continue
                    seen.add(fingerprint)
                    generated += 1
                    candidates.append(item)

                def label_item(
                    item: dict[str, Any],
                ) -> tuple[dict[str, dict[str, Any]], str | None]:
                    try:
                        if config.teacher == "llm":
                            return (
                                _labels_from_llm(
                                    questions,
                                    item.get("labels") or {},
                                    client.model,
                                ),
                                None,
                            )
                        if teacher is not None:
                            return teacher.label(item["state"], questions), None
                    except Exception as exc:
                        return {}, str(exc)
                    return {}, None

                if teacher is not None:
                    with ThreadPoolExecutor(
                        max_workers=max(
                            1,
                            min(settings.teacher_max_concurrency, len(candidates) or 1),
                        )
                    ) as pool:
                        labeled = list(pool.map(label_item, candidates))
                else:
                    labeled = [label_item(item) for item in candidates]

                for item, (labels, label_error) in zip(candidates, labeled, strict=False):
                    if not _wait_if_paused(db, job):
                        return
                    language_generated += 1
                    if label_error:
                        logger.warning("Teacher labeling failed: %s", label_error)
                        last_error = f"Teacher labeling failed: {label_error}"
                        rejected += 1
                        continue
                    sample = Sample(
                        project_id=project.id,
                        state=item["state"],
                        meta={
                            "promptVersion": "generation-v1",
                            "generationLanguage": language,
                            "teacher": config.teacher,
                        },
                        source="llm-generated",
                        generation_job_id=job.id,
                        language=item["language"],
                        difficulty=item["difficulty"],
                        status="pending",
                    )
                    db.add(sample)
                    db.flush()
                    for question in questions:
                        label = labels.get(question.key)
                        if not label:
                            continue
                        sample.annotations.append(
                            Annotation(
                                question_id=question.id,
                                answer=label["answer"],
                                teacher=label["teacher"],
                                teacher_model=label["teacher_model"],
                                confidence=label["confidence"],
                                probabilities=label["probabilities"],
                                status="pending",
                            )
                        )
                    db.commit()
                    accepted += 1

                _update(
                    db,
                    job,
                    stage="labeling" if teacher else "generating",
                    generated_count=generated,
                    accepted_count=accepted,
                    rejected_count=rejected,
                    progress=min(95, int(generated / max(1, config.count) * 95)),
                    error=last_error,
                )

        if accepted == 0:
            _update(
                db,
                job,
                status="failed",
                stage="failed",
                generated_count=generated,
                accepted_count=0,
                rejected_count=rejected,
                progress=100,
                error=last_error or "No samples were accepted",
                finished_at=_now(),
            )
            return
        _update(
            db,
            job,
            status="completed",
            stage="completed",
            generated_count=generated,
            accepted_count=accepted,
            rejected_count=rejected,
            progress=100,
            error=last_error,
            finished_at=_now(),
        )
    except Exception as exc:
        logger.exception("Generation job failed")
        job = db.get(GenerationJob, job_id)
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
        if client is not None:
            client.close()
        db.close()


def _allocate(total: int, languages: list[str]) -> dict[str, int]:
    base = total // len(languages)
    remainder = total % len(languages)
    return {
        language: base + (1 if index < remainder else 0) for index, language in enumerate(languages)
    }
