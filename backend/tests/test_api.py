from __future__ import annotations

import json

from fastapi.testclient import TestClient


def test_config_and_device(client: TestClient) -> None:
    response = client.get("/api/v1/config")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["targets"] == ["laya"]
    assert data["reservedTargets"] == ["gliner"]
    assert "cpu" in data["availableDevices"]
    assert data["llmModel"] == "deepseek-flash"

    updated = client.post("/api/v1/config/device", json={"device": "cpu"})
    assert updated.status_code == 200
    assert updated.json()["data"]["device"] == "cpu"


def test_seed_review_and_laya_export(client: TestClient, project_factory) -> None:
    project_id, _, _ = project_factory()
    imported = client.post(
        f"/api/v1/projects/{project_id}/seeds",
        json={
            "samples": [
                {
                    "state": {"ticket": "I was charged twice this month."},
                    "labels": {"team": "billing", "urgent": 0.93},
                    "language": "en",
                }
            ]
        },
    )
    assert imported.status_code == 201, imported.text
    seed_id = imported.json()[0]["id"]

    promoted = client.post(f"/api/v1/seeds/{seed_id}/promote")
    assert promoted.status_code == 200, promoted.text
    sample = promoted.json()
    assert sample["status"] == "pending"
    assert sample["annotationCount"] == 2

    accepted = client.post(f"/api/v1/samples/{sample['id']}/accept", json={})
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "accepted"

    snapshot = client.post(f"/api/v1/projects/{project_id}/datasets")
    assert snapshot.status_code == 201, snapshot.text
    body = snapshot.json()
    assert body["splitCounts"]["train"] == 1
    assert body["labelDistribution"]["team"]["billing"] == 1
    assert body["teacherModels"] == {"human": 2}

    laya_response = client.get(body["downloads"]["laya"])
    assert laya_response.status_code == 200
    laya = json.loads(laya_response.text.strip())
    assert laya["expected"] == {"team": "billing", "urgent": True}
    assert laya["gold"]["team"]["probabilities"]["billing"] == 1.0
    assert laya["gold"]["urgent"]["noul"] == 0.93
    assert laya["gold"]["urgent"]["probabilities"]["true"] == 0.93

    canonical_response = client.get(body["downloads"]["canonical"])
    canonical = json.loads(canonical_response.text.strip())
    assert canonical["questions"]["team"]["criteria"]["billing"] == "Refunds and payments"

    gliner_response = client.get(body["downloads"]["gliner"])
    gliner = json.loads(gliner_response.text.strip())
    assert gliner["output"]["classifications"][0]["true_label"] == ["billing"]
    assert gliner["output"]["classifications"][0]["type"] == "choice"
    assert gliner["output"]["classifications"][0]["prompt"] == "Which team should handle this?"
    assert gliner["input"].startswith("ticket:")


def test_missing_answer_blocks_accept_until_edited(client: TestClient, project_factory) -> None:
    project_id, _, urgent_id = project_factory()
    created = client.post(
        f"/api/v1/projects/{project_id}/samples",
        json={
            "state": {"ticket": "API is down"},
            "labels": {"team": "technical"},
        },
    )
    assert created.status_code == 201, created.text
    sample_id = created.json()["id"]
    assert created.json()["missingQuestionIds"] == [urgent_id]

    blocked = client.post(f"/api/v1/samples/{sample_id}/accept", json={})
    assert blocked.status_code == 422
    assert "urgent" in blocked.json()["error"]["message"]

    edited = client.put(
        f"/api/v1/samples/{sample_id}/annotations/{urgent_id}",
        json={"answer": "yes", "reviewer": "alice"},
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["answer"]["noul"] == 1.0
    assert edited.json()["reviewer"] == "alice"

    accepted = client.post(f"/api/v1/samples/{sample_id}/accept", json={})
    assert accepted.status_code == 200


def test_dataset_requires_accepted_samples(client: TestClient, project_factory) -> None:
    project_id, _, _ = project_factory()
    response = client.post(f"/api/v1/projects/{project_id}/datasets")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_question_validation_and_duplicate_keys(client: TestClient, project_factory) -> None:
    project_id, team_id, _ = project_factory()
    duplicate = client.post(
        f"/api/v1/projects/{project_id}/questions",
        json={"key": "team", "type": "noul", "instructions": "Duplicate"},
    )
    assert duplicate.status_code == 422

    invalid_choice = client.post(
        f"/api/v1/projects/{project_id}/questions",
        json={"key": "kind", "type": "choice", "criteria": {}},
    )
    assert invalid_choice.status_code == 422

    created = client.post(
        f"/api/v1/projects/{project_id}/samples",
        json={"state": {"ticket": "x"}, "labels": {"team": "billing"}},
    )
    assert created.status_code == 201
    type_change = client.put(
        f"/api/v1/projects/{project_id}/questions/{team_id}",
        json={"type": "noul", "criteria": None},
    )
    assert type_change.status_code == 422
    assert "annotations" in type_change.json()["error"]["message"]


def test_score_question_exports_ordinal_value(client: TestClient, project_factory) -> None:
    project_id, _, _ = project_factory()
    question = client.post(
        f"/api/v1/projects/{project_id}/questions",
        json={
            "key": "urgency",
            "type": "score",
            "instructions": "How urgent?",
            "criteria": ["can wait", "this week", "today"],
        },
    )
    assert question.status_code == 201, question.text
    created = client.post(
        f"/api/v1/projects/{project_id}/samples",
        json={
            "state": {"ticket": "Production outage"},
            "labels": {"team": "technical", "urgent": 1, "urgency": "today"},
        },
    )
    assert created.status_code == 201, created.text
    accepted = client.post(f"/api/v1/samples/{created.json()['id']}/accept", json={})
    assert accepted.status_code == 200, accepted.text
    snapshot = client.post(f"/api/v1/projects/{project_id}/datasets")
    assert snapshot.status_code == 201, snapshot.text
    laya = json.loads(client.get(snapshot.json()["downloads"]["laya"]).text.strip())
    assert laya["expected"]["urgency"] == 2
    assert laya["gold"]["urgency"]["score"] == 2


def test_snapshot_guarantees_holdout_splits(client: TestClient, project_factory) -> None:
    project_id, _, _ = project_factory()
    rows = [
        {
            "state": {"ticket": f"Unique support example number {index}"},
            "labels": {"team": "billing", "urgent": index % 2 == 0},
            "language": "en",
        }
        for index in range(12)
    ]
    seeds = client.post(f"/api/v1/projects/{project_id}/seeds", json={"samples": rows})
    assert seeds.status_code == 201
    for seed in seeds.json():
        sample = client.post(f"/api/v1/seeds/{seed['id']}/promote")
        assert sample.status_code == 200
        accepted = client.post(f"/api/v1/samples/{sample.json()['id']}/accept", json={})
        assert accepted.status_code == 200
    snapshot = client.post(f"/api/v1/projects/{project_id}/datasets")
    assert snapshot.status_code == 201, snapshot.text
    counts = snapshot.json()["splitCounts"]
    assert counts["train"] > 0
    assert counts["validation"] > 0
    assert counts["test"] > 0


def test_real_heldout_import_marks_test_split(client: TestClient, project_factory) -> None:
    project_id, _, _ = project_factory()
    imported = client.post(
        f"/api/v1/projects/{project_id}/heldout",
        json={
            "samples": [
                {
                    "state": {"ticket": "Held-out refund case"},
                    "labels": {"team": "billing", "urgent": 1},
                    "language": "en",
                }
            ]
        },
    )
    assert imported.status_code == 201, imported.text
    sample_id = imported.json()[0]["id"]
    accepted = client.post(f"/api/v1/samples/{sample_id}/accept", json={})
    assert accepted.status_code == 200
    snapshot = client.post(f"/api/v1/projects/{project_id}/datasets")
    assert snapshot.status_code == 201, snapshot.text
    assert snapshot.json()["splitCounts"]["test"] == 1
