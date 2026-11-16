from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.core.errors import ApiError
from app.models import Annotation, DatasetSnapshot, Project, Question, Sample


def _split_for(group: str) -> str:
    bucket = int(hashlib.sha256(group.encode("utf-8")).hexdigest()[:8], 16) % 100
    if bucket < 80:
        return "train"
    if bucket < 90:
        return "validation"
    return "test"


def _question_spec(question: Question) -> dict[str, Any]:
    spec: dict[str, Any] = {
        "type": question.type,
        "instructions": question.instructions,
    }
    if question.type == "choice":
        spec["criteria"] = question.criteria or {}
    elif question.type == "score" and question.criteria:
        spec["criteria"] = question.criteria
    return spec


def _expected(question: Question, answer: dict[str, Any]) -> Any:
    if question.type == "choice":
        return answer.get("choice")
    if question.type == "noul":
        return bool(float(answer.get("noul", 0)) >= 0.5)
    if question.type == "score":
        return answer.get("score")
    return None


def _canonical_row(
    sample: Sample,
    questions: list[Question],
    annotations: dict[str, Annotation],
    split: str,
) -> dict[str, Any]:
    gold: dict[str, Any] = {}
    teachers: list[str] = []
    for question in questions:
        annotation = annotations[question.id]
        gold[question.key] = annotation.answer
        teachers.append(annotation.teacher_model or annotation.teacher)

    meta = dict(sample.meta or {})
    meta.update(
        {
            "language": sample.language,
            "source": sample.source,
            "difficulty": sample.difficulty,
            "teachers": sorted(set(teachers)),
            "promptVersion": "schema-v1",
        }
    )
    return {
        "id": sample.id,
        "projectId": sample.project_id,
        "split": split,
        "state": sample.state,
        "questions": {question.key: _question_spec(question) for question in questions},
        "gold": gold,
        "meta": meta,
    }


def _laya_gold(question: Question, answer: dict[str, Any]) -> dict[str, Any] | None:
    if question.type == "choice":
        probabilities = answer.get("probabilities")
        if not isinstance(probabilities, dict):
            return None
        criteria = question.criteria if isinstance(question.criteria, dict) else {}
        values = {key: float(probabilities.get(key, 0.0)) for key in criteria}
        total = sum(values.values())
        if total <= 0:
            return None
        return {"probabilities": {key: value / total for key, value in values.items()}}
    if question.type == "noul":
        try:
            probability = float(answer.get("noul", 0.0))
        except (TypeError, ValueError):
            return None
        probability = max(0.0, min(1.0, probability))
        return {
            "noul": probability,
            "probabilities": {"false": 1.0 - probability, "true": probability},
        }
    if question.type == "score":
        labels = question.criteria if isinstance(question.criteria, list) else []
        if not labels:
            return None
        probabilities = answer.get("probabilities")
        values = []
        if isinstance(probabilities, dict):
            for index, label in enumerate(labels):
                value = probabilities.get(label, probabilities.get(str(index), 0.0))
                values.append(float(value))
        else:
            try:
                selected = int(round(float(answer.get("score"))))
            except (TypeError, ValueError):
                return None
            values = [1.0 if index == selected else 0.0 for index in range(len(labels))]
        total = sum(values)
        if total <= 0:
            return None
        return {
            "score": answer.get("score"),
            "probabilities": {str(index): value / total for index, value in enumerate(values)},
        }
    return None


def _laya_row(canonical: dict[str, Any], questions: list[Question]) -> dict[str, Any]:
    expected: dict[str, Any] = {}
    gold: dict[str, Any] = {}
    for key, answer in canonical["gold"].items():
        question = next(item for item in questions if item.key == key)
        expected[key] = _expected(question, answer)
        normalized = _laya_gold(question, answer)
        if normalized is not None:
            gold[key] = normalized
    return {
        "state": canonical["state"],
        "questions": canonical["questions"],
        "expected": expected,
        "gold": gold,
        "split": canonical["split"],
        "meta": canonical["meta"],
    }


def _state_text(state: dict[str, Any]) -> str:
    if not isinstance(state, dict):
        return str(state)
    if set(state) == {"text"}:
        return str(state["text"])
    lines = []
    for key, value in state.items():
        if isinstance(value, (dict, list)):
            rendered = json.dumps(value, ensure_ascii=False)
        else:
            rendered = str(value)
        lines.append(f"{key}: {rendered}")
    return "\n".join(lines)


def _gliner_row(canonical: dict[str, Any], questions: list[Question]) -> dict[str, Any]:
    classifications = []
    for question in questions:
        answer = canonical["gold"][question.key]
        prompt = question.instructions.strip()
        if question.type == "choice":
            criteria = question.criteria if isinstance(question.criteria, dict) else {}
            item: dict[str, Any] = {
                "task": question.key,
                "labels": list(criteria),
                "true_label": [answer["choice"]],
            }
            if criteria:
                item["label_descriptions"] = criteria
        elif question.type == "noul":
            item = {
                "task": question.key,
                "labels": ["yes", "no"],
                "true_label": ["yes" if float(answer["noul"]) >= 0.5 else "no"],
            }
        else:
            labels = (
                list(question.criteria)
                if isinstance(question.criteria, list)
                else [str(index) for index in range(6)]
            )
            selected = (
                labels[int(answer["score"])]
                if isinstance(question.criteria, list)
                else str(answer["score"])
            )
            item = {
                "task": question.key,
                "labels": labels,
                "true_label": [selected],
            }
        item["type"] = question.type
        if prompt:
            item["prompt"] = prompt
        classifications.append(item)
    return {
        "input": _state_text(canonical["state"]),
        "output": {"classifications": classifications},
        "meta": {"split": canonical["split"], "language": canonical["meta"]["language"]},
    }


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def freeze_snapshot(db: Session, project: Project, questions: list[Question]) -> DatasetSnapshot:
    if not questions:
        raise ApiError(
            422,
            "VALIDATION_ERROR",
            "Add at least one question before freezing a dataset",
        )

    samples = db.scalars(
        select(Sample)
        .where(Sample.project_id == project.id, Sample.status == "accepted")
        .options(selectinload(Sample.annotations))
        .order_by(Sample.created_at)
    ).all()
    if not samples:
        raise ApiError(
            422,
            "VALIDATION_ERROR",
            "No accepted samples are available. Review and accept samples first.",
        )

    incomplete: list[str] = []
    complete: list[tuple[Sample, dict[str, Annotation], str]] = []
    for sample in samples:
        annotations = {annotation.question_id: annotation for annotation in sample.annotations}
        missing = [question.id for question in questions if question.id not in annotations]
        if missing:
            incomplete.append(sample.id)
            continue
        group = str((sample.meta or {}).get("seedId") or sample.id)
        complete.append((sample, annotations, group))

    if incomplete:
        raise ApiError(
            422,
            "VALIDATION_ERROR",
            "Accepted samples are missing accepted answers. Open them in review and accept again.",
            {"sampleIds": incomplete},
        )

    heldout_ids = {sample.id for sample, _, _ in complete if (sample.meta or {}).get("heldout")}
    training_samples = [sample for sample, _, _ in complete if sample.id not in heldout_ids]
    force_train = len(training_samples) < 5
    group_samples: dict[str, list[str]] = {}
    splits: dict[str, str] = {}
    for sample, _, group in complete:
        group_samples.setdefault(group, []).append(sample.id)
        if sample.id in heldout_ids:
            splits[sample.id] = "test"
        else:
            splits[sample.id] = "train" if force_train else _split_for(group)

    def move_group(target: str) -> bool:
        candidates = [
            group
            for group, sample_ids in group_samples.items()
            if len(group_samples) > 1
            and not any(sample_id in heldout_ids for sample_id in sample_ids)
            and all(splits[sample_id] == "train" for sample_id in sample_ids)
        ]
        candidates.sort(key=lambda group: len(group_samples[group]))
        if not candidates:
            return False
        for sample_id in group_samples[candidates[0]]:
            splits[sample_id] = target
        return True

    counts = Counter(splits.values())
    if not force_train and counts["test"] == 0:
        move_group("test")
    if len(training_samples) >= 10 and Counter(splits.values())["validation"] == 0:
        move_group("validation")

    rows_by_logical_split: dict[str, list[dict[str, Any]]] = {
        "train": [],
        "validation": [],
        "test": [],
    }
    canonical_rows: list[dict[str, Any]] = []
    laya_rows: list[dict[str, Any]] = []
    gliner_rows: list[dict[str, Any]] = []
    label_distribution: dict[str, Counter[str]] = {
        question.key: Counter() for question in questions
    }
    teacher_counts: Counter[str] = Counter()

    for sample, annotations, _ in complete:
        split = splits[sample.id]
        canonical = _canonical_row(sample, questions, annotations, split)
        laya = _laya_row(canonical, questions)
        gliner = _gliner_row(canonical, questions)
        canonical_rows.append(canonical)
        laya_rows.append(laya)
        gliner_rows.append(gliner)
        rows_by_logical_split[split].append(canonical)
        for question in questions:
            answer = canonical["gold"][question.key]
            if question.type == "choice":
                label_distribution[question.key][str(answer["choice"])] += 1
            elif question.type == "noul":
                label_distribution[question.key][
                    "yes" if float(answer["noul"]) >= 0.5 else "no"
                ] += 1
            else:
                label_distribution[question.key][str(answer["score"])] += 1
            annotation = annotations[question.id]
            teacher_counts[annotation.teacher_model or annotation.teacher] += 1

    settings = get_settings()
    version = (
        db.scalar(
            select(func.max(DatasetSnapshot.version)).where(
                DatasetSnapshot.project_id == project.id
            )
        )
        or 0
    ) + 1
    directory = settings.resolved_dataset_dir / project.id / f"v{version}"
    directory.mkdir(parents=True, exist_ok=True)
    canonical_path = directory / "canonical.jsonl"
    laya_path = directory / "laya.jsonl"
    gliner_path = directory / "gliner.jsonl"
    _write_jsonl(canonical_path, canonical_rows)
    _write_jsonl(laya_path, laya_rows)
    _write_jsonl(gliner_path, gliner_rows)

    snapshot = DatasetSnapshot(
        project_id=project.id,
        version=version,
        canonical_path=str(canonical_path),
        laya_path=str(laya_path),
        gliner_path=str(gliner_path),
        split_counts={key: len(value) for key, value in rows_by_logical_split.items()},
        label_distribution={
            key: dict(sorted(counter.items())) for key, counter in label_distribution.items()
        },
        prompt_versions={"schema": "v1"},
        teacher_models=dict(sorted(teacher_counts.items())),
    )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    return snapshot
