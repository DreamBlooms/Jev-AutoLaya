from __future__ import annotations

import json
import time
from collections.abc import Iterator

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import project_or_404
from app.core.config import get_settings
from app.core.database import SessionLocal, get_db
from app.core.errors import ApiError
from app.models import GenerationJob, Project, SeedSample
from app.schemas.jobs import (
    GenerationJobOut,
    GenerationPreviewOut,
    GenerationPromptDefaultsOut,
    GenerationRequest,
)
from app.services.generation.prompts import (
    PromptTemplateError,
    build_messages,
    prompt_template_defaults,
)
from app.services.generation.runner import create_generation_job
from app.services.job_worker import wake_job_worker
from app.services.llm.openai_compat import build_chat_payload, chat_completions_url

router = APIRouter(tags=["generation"])

TERMINAL = {"completed", "failed", "cancelled"}


@router.post(
    "/projects/{project_id}/generate",
    response_model=GenerationJobOut,
    status_code=status.HTTP_202_ACCEPTED,
)
def generate(
    payload: GenerationRequest,
    project: Project = Depends(project_or_404),
    db: Session = Depends(get_db),
) -> GenerationJob:
    return create_generation_job(db, project, payload)


@router.get(
    "/projects/{project_id}/generation-prompt-defaults",
    response_model=GenerationPromptDefaultsOut,
)
def generation_prompt_defaults(
    project: Project = Depends(project_or_404),
) -> GenerationPromptDefaultsOut:
    del project
    return GenerationPromptDefaultsOut(**prompt_template_defaults())


@router.post(
    "/projects/{project_id}/generation-preview",
    response_model=GenerationPreviewOut,
)
def preview_generation(
    payload: GenerationRequest,
    project: Project = Depends(project_or_404),
    db: Session = Depends(get_db),
) -> GenerationPreviewOut:
    questions = list(project.questions)
    if not questions:
        raise ApiError(422, "VALIDATION_ERROR", "Add at least one question before generating")
    seeds = list(db.scalars(select(SeedSample).where(SeedSample.project_id == project.id)))
    settings = get_settings()
    languages = [language for language in payload.languages if language] or ["en"]
    language = languages[0]
    batch_size = min(settings.generation_batch_size, payload.count)
    try:
        messages = build_messages(
            project=project,
            questions=questions,
            seeds=seeds,
            count=batch_size,
            language=language,
            difficulty=payload.difficulty,
            negative_ratio=payload.negative_ratio,
            label_balanced=payload.label_balanced,
            label_with_llm=payload.teacher == "llm",
            custom_prompt=payload.custom_prompt,
            system_prompt_template=payload.system_prompt_template,
            user_prompt_template=payload.user_prompt_template,
        )
    except PromptTemplateError as exc:
        raise ApiError(422, "VALIDATION_ERROR", str(exc)) from exc
    override = payload.llm
    model = override.model if override and override.model else settings.llm_model
    base_url = override.base_url if override and override.base_url else settings.llm_base_url
    body = build_chat_payload(
        model=model,
        messages=messages,
        temperature=(
            override.temperature
            if override and override.temperature is not None
            else settings.llm_temperature
        ),
        max_tokens=(
            override.max_tokens if override and override.max_tokens else settings.llm_max_tokens
        ),
        think_budget=override.think_budget if override else None,
        think_level=override.think_level if override else None,
        json_mode=True,
    )
    return GenerationPreviewOut(
        model=model,
        endpoint=chat_completions_url(base_url),
        language=language,
        batch_size=batch_size,
        body=body,
    )


@router.get("/generation-jobs", response_model=list[GenerationJobOut])
def list_generation_jobs(
    project_id: str | None = Query(default=None, alias="projectId"),
    db: Session = Depends(get_db),
) -> list[GenerationJob]:
    query = select(GenerationJob)
    if project_id:
        query = query.where(GenerationJob.project_id == project_id)
    return list(db.scalars(query.order_by(GenerationJob.created_at.desc()).limit(50)))


@router.get("/generation-jobs/{job_id}", response_model=GenerationJobOut)
def get_generation_job(job_id: str, db: Session = Depends(get_db)) -> GenerationJob:
    job = db.get(GenerationJob, job_id)
    if job is None:
        raise ApiError(404, "NOT_FOUND", "Generation job not found")
    return job


@router.get("/generation-jobs/{job_id}/events")
def generation_events(job_id: str) -> StreamingResponse:
    def stream() -> Iterator[str]:
        while True:
            db = SessionLocal()
            try:
                job = db.get(GenerationJob, job_id)
                if job is None:
                    yield f"data: {json.dumps({'error': 'not_found'})}\n\n"
                    return
                payload = GenerationJobOut.model_validate(job).model_dump(
                    by_alias=True, mode="json"
                )
            finally:
                db.close()
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            if payload["status"] in TERMINAL:
                return
            time.sleep(1)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/generation-jobs/{job_id}/pause", response_model=GenerationJobOut)
def pause_generation_job(job_id: str, db: Session = Depends(get_db)) -> GenerationJob:
    job = db.get(GenerationJob, job_id)
    if job is None:
        raise ApiError(404, "NOT_FOUND", "Generation job not found")
    if job.status in TERMINAL or job.status == "paused":
        return job
    job.status = "paused"
    job.stage = "paused"
    db.commit()
    db.refresh(job)
    return job


@router.post("/generation-jobs/{job_id}/resume", response_model=GenerationJobOut)
def resume_generation_job(job_id: str, db: Session = Depends(get_db)) -> GenerationJob:
    job = db.get(GenerationJob, job_id)
    if job is None:
        raise ApiError(404, "NOT_FOUND", "Generation job not found")
    if job.status != "paused":
        return job
    job.status = "pending" if job.started_at is None else "running"
    job.stage = "generating"
    db.commit()
    db.refresh(job)
    wake_job_worker()
    return job


@router.post("/generation-jobs/{job_id}/cancel", response_model=GenerationJobOut)
def cancel_generation_job(
    job_id: str,
    db: Session = Depends(get_db),
) -> GenerationJob:
    job = db.get(GenerationJob, job_id)
    if job is None:
        raise ApiError(404, "NOT_FOUND", "Generation job not found")
    if job.status in TERMINAL:
        return job
    job.cancel_requested = True
    if job.status in {"pending", "paused"} and job.started_at is None:
        job.status = "cancelled"
        job.stage = "cancelled"
    db.commit()
    db.refresh(job)
    return job
