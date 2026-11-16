from __future__ import annotations

import threading
import time

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import Annotation, GenerationJob, Project, Question, Sample
from app.schemas.jobs import GenerationRequest
from app.services.evaluation.metrics import aggregate
from app.services.generation.parser import parse_states
from app.services.generation.prompts import build_messages
from app.services.teachers.jev import JevTeacher


class FakeTransport:
    def ask(self, *, model: str, state: dict, questions: dict) -> dict:
        return {
            "model": model,
            "answers": {
                "team": {
                    "type": "choice",
                    "choice": "billing",
                    "confidence": 0.91,
                    "probabilities": {
                        "billing": 0.91,
                        "technical": 0.06,
                        "sales": 0.03,
                    },
                },
                "urgent": {"type": "noul", "noul": 0.8, "confidence": 0.8},
            },
        }


class FakeLLM:
    def __init__(self, **kwargs) -> None:
        pass

    def chat_json(self, messages):
        return {
            "samples": [
                {
                    "state": {"ticket": "I was charged twice, please refund."},
                    "language": "en",
                    "difficulty": "easy",
                },
                {
                    "state": {"ticket": "The API returns 500 after login."},
                    "language": "en",
                    "difficulty": "medium",
                },
            ]
        }

    def close(self) -> None:
        pass


class FakeTeacher:
    def __init__(self) -> None:
        pass

    def label(self, state, questions):
        return {
            "team": {
                "answer": {
                    "choice": "billing",
                    "confidence": 0.9,
                    "probabilities": {"billing": 0.9, "technical": 0.07, "sales": 0.03},
                },
                "teacher": "jev",
                "teacher_model": "fake-jev",
                "confidence": 0.9,
                "probabilities": {"billing": 0.9, "technical": 0.07, "sales": 0.03},
            },
            "urgent": {
                "answer": {
                    "noul": 0.4,
                    "confidence": 0.6,
                    "probabilities": {"yes": 0.4, "no": 0.6},
                },
                "teacher": "jev",
                "teacher_model": "fake-jev",
                "confidence": 0.6,
                "probabilities": {"yes": 0.4, "no": 0.6},
            },
        }


def test_generation_prompt_and_parser() -> None:
    project = Project(name="Support", domain="Tickets", languages=["en"])
    question = Question(
        key="team", type="choice", instructions="Which team?", criteria={"billing": "payments"}
    )
    messages = build_messages(
        project=project,
        questions=[question],
        seeds=[],
        count=2,
        language="en",
        difficulty={"easy": 1.0},
        negative_ratio=0.1,
        label_balanced=True,
    )
    assert "Support" in messages[1]["content"]
    assert '"billing"' in messages[1]["content"]

    states = parse_states(
        {
            "samples": [
                {"state": {"ticket": "A valid ticket"}, "language": "en", "difficulty": "easy"},
                {"state": {"ticket": "A valid ticket"}, "language": "en"},
                {"state": {}},
            ]
        },
        language="en",
    )
    assert len(states) == 1
    assert states[0]["difficulty"] == "easy"


def test_jev_teacher_normalizes_answers() -> None:
    questions = [
        Question(
            key="team",
            type="choice",
            instructions="Which team?",
            criteria={"billing": "payments", "technical": "bugs", "sales": "pricing"},
        ),
        Question(key="urgent", type="noul", instructions="Urgent?"),
    ]
    teacher = JevTeacher(transport=FakeTransport())
    labels = teacher.label({"ticket": "refund"}, questions)
    assert labels["team"]["answer"]["choice"] == "billing"
    assert labels["team"]["teacher_model"] == "jev-1.14.0"
    assert labels["urgent"]["answer"]["noul"] == 0.8


def test_generation_runner_persists_samples(monkeypatch, client: TestClient) -> None:
    project = client.post(
        "/api/v1/projects",
        json={"name": "P2", "domain": "Tickets", "languages": ["en"]},
    ).json()
    project_id = project["id"]
    client.post(
        f"/api/v1/projects/{project_id}/questions",
        json={
            "key": "team",
            "type": "choice",
            "instructions": "Which team?",
            "criteria": {"billing": "payments", "technical": "bugs", "sales": "pricing"},
        },
    )
    client.post(
        f"/api/v1/projects/{project_id}/questions",
        json={"key": "urgent", "type": "noul", "instructions": "Urgent?"},
    )
    db = SessionLocal()
    try:
        job = GenerationJob(
            project_id=project_id,
            status="pending",
            target_count=2,
            config=GenerationRequest(count=2, languages=["en"], teacher="jev").model_dump(),
        )
        db.add(job)
        db.commit()
        job_id = job.id
    finally:
        db.close()

    from app.services.generation import runner

    monkeypatch.setattr(runner, "OpenAICompatibleClient", FakeLLM)
    monkeypatch.setattr(runner, "JevTeacher", FakeTeacher)
    runner.run_generation_job(job_id)

    db = SessionLocal()
    try:
        job = db.get(GenerationJob, job_id)
        assert job is not None
        assert job.status == "completed"
        assert job.accepted_count == 2
        samples = db.scalars(select(Sample).where(Sample.generation_job_id == job_id)).all()
        assert len(samples) == 2
        annotations = db.scalars(
            select(Annotation).where(Annotation.sample_id == samples[0].id)
        ).all()
        assert len(annotations) == 2
        assert annotations[0].teacher == "jev"
    finally:
        db.close()


def test_metrics_aggregate() -> None:
    rows = [
        {
            "questions": {
                "team": {"type": "choice"},
                "urgent": {"type": "noul"},
            },
            "expected": {"team": "billing", "urgent": True},
        },
        {
            "questions": {
                "team": {"type": "choice"},
                "urgent": {"type": "noul"},
            },
            "expected": {"team": "technical", "urgent": False},
        },
    ]
    predictions = [
        {
            "answers": {
                "team": {
                    "choice": "billing",
                    "confidence": 0.9,
                    "probabilities": {"billing": 0.9, "technical": 0.1},
                },
                "urgent": {"noul": 0.8, "probabilities": {"false": 0.2, "true": 0.8}},
            },
            "elapsed_ms": 10,
        },
        {
            "answers": {
                "team": {
                    "choice": "billing",
                    "confidence": 0.8,
                    "probabilities": {"billing": 0.8, "technical": 0.2},
                },
                "urgent": {"noul": 0.3, "probabilities": {"false": 0.7, "true": 0.3}},
            },
            "elapsed_ms": 20,
        },
    ]
    result = aggregate(rows, predictions)
    assert result["n"] == 2
    assert result["questions"]["team"]["accuracy"] == 0.5
    assert result["questions"]["urgent"]["accuracy"] == 1.0
    assert result["latency_p50_ms"] is not None


def test_reannotate_endpoint(client: TestClient, project_factory, monkeypatch) -> None:
    project_id, _, _ = project_factory()
    created = client.post(
        f"/api/v1/projects/{project_id}/samples",
        json={"state": {"ticket": "refund please"}, "labels": {"team": "billing", "urgent": 0}},
    )
    sample_id = created.json()["id"]
    blocked = client.post(f"/api/v1/samples/{sample_id}/reannotate")
    assert blocked.status_code == 400
    assert blocked.json()["error"]["code"] == "TEACHER_ERROR"

    from app.api.routes import samples as sample_routes

    monkeypatch.setattr(sample_routes, "JevTeacher", FakeTeacher)
    refreshed = client.post(f"/api/v1/samples/{sample_id}/reannotate")
    assert refreshed.status_code == 200, refreshed.text
    assert refreshed.json()["status"] == "pending"
    assert refreshed.json()["annotations"][0]["teacher"] == "jev"


class FakeLabelingLLM:
    model = "fake-llm"

    def __init__(self, **kwargs) -> None:
        pass

    def chat_json(self, messages):
        assert '"labels"' in messages[1]["content"]
        return {
            "samples": [
                {
                    "state": {"ticket": "I was charged twice, please refund."},
                    "language": "en",
                    "difficulty": "easy",
                    "labels": {
                        "team": {"choice": "billing", "confidence": 0.8},
                        "urgent": {"noul": 0.7, "confidence": 0.7},
                    },
                }
            ]
        }

    def close(self) -> None:
        pass


def test_llm_direct_labels_are_saved(monkeypatch, client: TestClient) -> None:
    project = client.post(
        "/api/v1/projects",
        json={"name": "LLM labels", "domain": "Tickets", "languages": ["en"]},
    ).json()
    project_id = project["id"]
    client.post(
        f"/api/v1/projects/{project_id}/questions",
        json={
            "key": "team",
            "type": "choice",
            "instructions": "Which team?",
            "criteria": {"billing": "payments", "technical": "bugs", "sales": "pricing"},
        },
    )
    client.post(
        f"/api/v1/projects/{project_id}/questions",
        json={"key": "urgent", "type": "noul", "instructions": "Urgent?"},
    )
    db = SessionLocal()
    try:
        job = GenerationJob(
            project_id=project_id,
            status="pending",
            target_count=1,
            config=GenerationRequest(
                count=1,
                languages=["en"],
                teacher="llm",
            ).model_dump(),
        )
        db.add(job)
        db.commit()
        job_id = job.id
    finally:
        db.close()

    from app.services.generation import runner

    monkeypatch.setattr(runner, "OpenAICompatibleClient", FakeLabelingLLM)
    runner.run_generation_job(job_id)

    db = SessionLocal()
    try:
        job = db.get(GenerationJob, job_id)
        assert job is not None
        assert job.status == "completed"
        assert job.accepted_count == 1
        sample = db.scalar(select(Sample).where(Sample.generation_job_id == job_id))
        assert sample is not None
        annotations = db.scalars(select(Annotation).where(Annotation.sample_id == sample.id)).all()
        assert {annotation.teacher for annotation in annotations} == {"llm"}
        assert {annotation.teacher_model for annotation in annotations} == {"fake-llm"}
        assert sample.meta["teacher"] == "llm"
    finally:
        db.close()


class ConcurrentTeacher:
    active = 0
    max_active = 0
    lock = threading.Lock()

    def __init__(self) -> None:
        pass

    def label(self, state, questions):
        with self.lock:
            ConcurrentTeacher.active += 1
            ConcurrentTeacher.max_active = max(
                ConcurrentTeacher.max_active, ConcurrentTeacher.active
            )
        time.sleep(0.15)
        with self.lock:
            ConcurrentTeacher.active -= 1
        return {
            "team": {
                "answer": {
                    "choice": "billing",
                    "confidence": 0.9,
                    "probabilities": {"billing": 0.9, "technical": 0.1},
                },
                "teacher": "jev",
                "teacher_model": "fake-jev",
                "confidence": 0.9,
                "probabilities": {"billing": 0.9, "technical": 0.1},
            },
            "urgent": {
                "answer": {
                    "noul": 0.5,
                    "confidence": 0.5,
                    "probabilities": {"yes": 0.5, "no": 0.5},
                },
                "teacher": "jev",
                "teacher_model": "fake-jev",
                "confidence": 0.5,
                "probabilities": {"yes": 0.5, "no": 0.5},
            },
        }


def test_teacher_labeling_runs_concurrently(monkeypatch, client: TestClient) -> None:
    project = client.post(
        "/api/v1/projects",
        json={"name": "Concurrent", "domain": "Tickets", "languages": ["en"]},
    ).json()
    project_id = project["id"]
    client.post(
        f"/api/v1/projects/{project_id}/questions",
        json={
            "key": "team",
            "type": "choice",
            "instructions": "Which team?",
            "criteria": {"billing": "payments", "technical": "bugs"},
        },
    )
    client.post(
        f"/api/v1/projects/{project_id}/questions",
        json={"key": "urgent", "type": "noul", "instructions": "Urgent?"},
    )
    db = SessionLocal()
    try:
        job = GenerationJob(
            project_id=project_id,
            status="pending",
            target_count=4,
            config=GenerationRequest(
                count=4,
                languages=["en"],
                teacher="jev",
            ).model_dump(),
        )
        db.add(job)
        db.commit()
        job_id = job.id
    finally:
        db.close()

    class ManyLLM(FakeLLM):
        def chat_json(self, messages):
            return {
                "samples": [
                    {
                        "state": {"ticket": f"Concurrent ticket {index}"},
                        "language": "en",
                        "difficulty": "easy",
                    }
                    for index in range(4)
                ]
            }

    from app.services.generation import runner

    ConcurrentTeacher.active = 0
    ConcurrentTeacher.max_active = 0
    monkeypatch.setattr(runner, "OpenAICompatibleClient", ManyLLM)
    monkeypatch.setattr(runner, "JevTeacher", ConcurrentTeacher)
    runner.run_generation_job(job_id)
    assert ConcurrentTeacher.max_active > 1
    db = SessionLocal()
    try:
        job = db.get(GenerationJob, job_id)
        assert job is not None
        assert job.accepted_count == 4
    finally:
        db.close()
