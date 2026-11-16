from __future__ import annotations

from app.models import Annotation, DatasetSnapshot, Project, Sample
from app.schemas.dataset import DatasetSnapshotOut
from app.schemas.project import ProjectOut
from app.schemas.sample import AnnotationOut, SampleDetail, SampleOut
from app.services.runtime import get_device_preference


def project_out(project: Project) -> ProjectOut:
    return ProjectOut(
        id=project.id,
        name=project.name,
        domain=project.domain,
        languages=project.languages,
        question_count=len(project.questions),
        seed_count=len(project.seeds),
        sample_count=len(project.samples),
        pending_count=sum(1 for sample in project.samples if sample.status == "pending"),
        snapshot_count=len(project.snapshots),
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


def annotation_out(annotation: Annotation) -> AnnotationOut:
    return AnnotationOut(
        id=annotation.id,
        question_id=annotation.question_id,
        question_key=annotation.question.key,
        question_type=annotation.question.type,
        answer=annotation.answer,
        teacher=annotation.teacher,
        teacher_model=annotation.teacher_model,
        confidence=annotation.confidence,
        probabilities=annotation.probabilities,
        status=annotation.status,
        reviewer=annotation.reviewer,
        review_note=annotation.review_note,
        created_at=annotation.created_at,
        updated_at=annotation.updated_at,
    )


def sample_out(sample: Sample) -> SampleOut:
    return SampleOut(
        id=sample.id,
        project_id=sample.project_id,
        state=sample.state,
        meta=sample.meta,
        source=sample.source,
        generation_job_id=sample.generation_job_id,
        language=sample.language,
        difficulty=sample.difficulty,
        status=sample.status,
        annotation_count=len(sample.annotations),
        created_at=sample.created_at,
        updated_at=sample.updated_at,
    )


def sample_detail(sample: Sample, questions: list) -> SampleDetail:
    annotations = [annotation_out(annotation) for annotation in sample.annotations]
    annotated_question_ids = {annotation.question_id for annotation in sample.annotations}
    return SampleDetail(
        **sample_out(sample).model_dump(),
        annotations=annotations,
        questions=questions,
        missing_question_ids=[
            question.id for question in questions if question.id not in annotated_question_ids
        ],
    )


def snapshot_out(snapshot: DatasetSnapshot) -> DatasetSnapshotOut:
    prefix = f"/api/v1/datasets/{snapshot.id}/download"
    return DatasetSnapshotOut(
        id=snapshot.id,
        project_id=snapshot.project_id,
        version=snapshot.version,
        canonical_path=snapshot.canonical_path,
        laya_path=snapshot.laya_path,
        gliner_path=snapshot.gliner_path,
        split_counts=snapshot.split_counts,
        label_distribution=snapshot.label_distribution,
        prompt_versions=snapshot.prompt_versions,
        teacher_models=snapshot.teacher_models,
        created_at=snapshot.created_at,
        downloads={
            "canonical": f"{prefix}?format=canonical",
            "laya": f"{prefix}?format=laya",
            "gliner": f"{prefix}?format=gliner",
        },
    )


def config_out() -> dict:
    from app.schemas.config import RuntimeConfigOut
    from app.services.runtime import runtime_summary

    summary = runtime_summary()
    summary["device_preference"] = get_device_preference()
    return RuntimeConfigOut(**summary).model_dump(by_alias=True)
