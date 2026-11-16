from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.models import ModelArtifact, TrainingJob


def _accept_seed(client: TestClient, project_id: str, text: str) -> str:
    created = client.post(
        f"/api/v1/projects/{project_id}/samples",
        json={
            "state": {"ticket": text},
            "labels": {"team": "billing", "urgent": 0.2},
            "language": "en",
        },
    )
    assert created.status_code == 201, created.text
    sample_id = created.json()["id"]
    accepted = client.post(f"/api/v1/samples/{sample_id}/accept", json={})
    assert accepted.status_code == 200, accepted.text
    return sample_id


def test_sample_templates_and_import(client: TestClient, project_factory) -> None:
    project_id, _, _ = project_factory()

    jsonl_template = client.get(f"/api/v1/projects/{project_id}/samples/template?format=jsonl")
    assert jsonl_template.status_code == 200
    assert "state" in jsonl_template.text
    assert "jsonl" in jsonl_template.headers["content-disposition"]

    csv_template = client.get(f"/api/v1/projects/{project_id}/samples/template?format=csv")
    assert csv_template.status_code == 200
    assert csv_template.text.lstrip("\ufeff").startswith("state,labels")

    jsonl = "\n".join(
        [
            json.dumps(
                {
                    "state": {"ticket": "Imported JSONL refund"},
                    "labels": {"team": "billing"},
                    "language": "en",
                    "difficulty": "easy",
                }
            ),
            json.dumps(
                {
                    "state": {"ticket": "Imported held-out ticket"},
                    "labels": {"team": "technical"},
                    "language": "en",
                    "heldout": True,
                }
            ),
        ]
    ).encode()
    imported = client.post(
        f"/api/v1/projects/{project_id}/samples/import",
        files={"file": ("samples.jsonl", jsonl, "application/x-ndjson")},
    )
    assert imported.status_code == 201, imported.text
    body = imported.json()
    assert body["imported"] == 2
    assert body["heldout"] == 1
    assert body["samples"][0]["source"] == "import-jsonl"
    assert body["samples"][1]["meta"]["heldout"] is True

    csv_data = (
        "\ufeffstate,labels,language,difficulty,heldout\n"
        '"ticket: CSV imported ticket","{""team"": ""billing""}",zh,medium,false\n'
    ).encode()
    imported_csv = client.post(
        f"/api/v1/projects/{project_id}/samples/import",
        files={"file": ("samples.csv", csv_data, "text/csv")},
    )
    assert imported_csv.status_code == 201, imported_csv.text
    assert imported_csv.json()["imported"] == 1
    assert imported_csv.json()["samples"][0]["state"] == {"text": "ticket: CSV imported ticket"}

    invalid = client.post(
        f"/api/v1/projects/{project_id}/samples/import",
        files={
            "file": (
                "bad.jsonl",
                b'{"state":{"ticket":"x"},"labels":{"unknown":"x"}}\n',
                "application/x-ndjson",
            )
        },
    )
    assert invalid.status_code == 422
    assert "unknown question keys" in invalid.json()["error"]["message"]


def test_snapshot_delete_and_versioning(client: TestClient, project_factory) -> None:
    project_id, _, _ = project_factory()
    _accept_seed(client, project_id, "Snapshot delete candidate")

    first = client.post(f"/api/v1/projects/{project_id}/datasets")
    second = client.post(f"/api/v1/projects/{project_id}/datasets")
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json()["version"] == 1
    assert second.json()["version"] == 2
    first_path = Path(first.json()["canonicalPath"])

    deleted = client.delete(f"/api/v1/datasets/{first.json()['id']}")
    assert deleted.status_code == 200, deleted.text
    assert not first_path.exists()
    assert client.get(f"/api/v1/datasets/{first.json()['id']}").status_code == 404

    third = client.post(f"/api/v1/projects/{project_id}/datasets")
    assert third.status_code == 201, third.text
    assert third.json()["version"] == 3

    project = client.get(f"/api/v1/projects/{project_id}").json()
    assert project["snapshotCount"] == 2


def test_artifact_download_returns_zip(
    client: TestClient,
    project_factory,
    tmp_path: Path,
) -> None:
    project_id, _, _ = project_factory()
    artifact_dir = tmp_path / "checkpoint"
    artifact_dir.mkdir()
    (artifact_dir / "config.json").write_text('{"model":"test"}', encoding="utf-8")

    db = SessionLocal()
    try:
        artifact = ModelArtifact(
            project_id=project_id,
            target="laya",
            name="Test checkpoint",
            kind="checkpoint",
            path=str(artifact_dir),
            metrics={},
            config={},
        )
        db.add(artifact)
        db.commit()
        db.refresh(artifact)
        artifact_id = artifact.id
    finally:
        db.close()

    response = client.get(f"/api/v1/artifacts/{artifact_id}/download")
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        assert "checkpoint/config.json" in archive.namelist()
        assert json.loads(archive.read("checkpoint/config.json")) == {"model": "test"}


def test_snapshot_delete_blocked_by_active_job(client: TestClient, project_factory) -> None:
    project_id, _, _ = project_factory()
    _accept_seed(client, project_id, "Active snapshot")
    snapshot = client.post(f"/api/v1/projects/{project_id}/datasets")
    assert snapshot.status_code == 201, snapshot.text
    snapshot_id = snapshot.json()["id"]

    db = SessionLocal()
    try:
        db.add(
            TrainingJob(
                project_id=project_id,
                snapshot_id=snapshot_id,
                target="laya",
                mode="fit",
                device="cpu",
                status="pending",
                stage="queued",
                config={},
            )
        )
        db.commit()
    finally:
        db.close()

    blocked = client.delete(f"/api/v1/datasets/{snapshot_id}")
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "SNAPSHOT_IN_USE"


def test_evaluation_artifact_override_validation(client: TestClient, project_factory) -> None:
    project_id, _, _ = project_factory()
    _accept_seed(client, project_id, "Evaluation artifact validation")
    snapshot = client.post(f"/api/v1/projects/{project_id}/datasets")
    assert snapshot.status_code == 201, snapshot.text
    snapshot_id = snapshot.json()["id"]

    db = SessionLocal()
    try:
        artifact = ModelArtifact(
            project_id=project_id,
            target="laya",
            name="Wrong kind",
            kind="calibration",
            path="/tmp/not-used",
            metrics={},
            config={},
        )
        db.add(artifact)
        db.commit()
        db.refresh(artifact)
        artifact_id = artifact.id
    finally:
        db.close()

    missing = client.post(
        "/api/v1/evaluations",
        json={
            "projectId": project_id,
            "snapshotId": snapshot_id,
            "models": ["laya-finetuned"],
            "artifactIds": {"laya-finetuned": "missing"},
        },
    )
    assert missing.status_code == 404

    wrong_kind = client.post(
        "/api/v1/evaluations",
        json={
            "projectId": project_id,
            "snapshotId": snapshot_id,
            "models": ["laya-finetuned"],
            "artifactIds": {"laya-finetuned": artifact_id},
        },
    )
    assert wrong_kind.status_code == 422
    assert "not a checkpoint" in wrong_kind.json()["error"]["message"]

    unselected = client.post(
        "/api/v1/evaluations",
        json={
            "projectId": project_id,
            "snapshotId": snapshot_id,
            "models": ["laya-base"],
            "artifactIds": {"laya-finetuned": artifact_id},
        },
    )
    assert unselected.status_code == 422
    assert "unselected model" in unselected.json()["error"]["message"]


def test_seed_templates_and_import(client: TestClient, project_factory) -> None:
    project_id, _, _ = project_factory()

    jsonl_template = client.get(f"/api/v1/projects/{project_id}/seeds/template?format=jsonl")
    assert jsonl_template.status_code == 200
    assert "state" in jsonl_template.text
    assert "seeds-template" in jsonl_template.headers["content-disposition"]

    csv_template = client.get(f"/api/v1/projects/{project_id}/seeds/template?format=csv")
    assert csv_template.status_code == 200
    assert csv_template.text.lstrip("\ufeff").startswith("state,labels,language")

    jsonl = "\n".join(
        [
            json.dumps(
                {
                    "state": {"ticket": "Seed JSONL refund"},
                    "labels": {"team": "billing"},
                    "language": "en",
                }
            ),
            json.dumps(
                {
                    "state": {"ticket": "Seed JSONL outage"},
                    "labels": {"team": "technical"},
                    "language": "en",
                }
            ),
        ]
    ).encode()
    imported = client.post(
        f"/api/v1/projects/{project_id}/seeds/import",
        files={"file": ("seeds.jsonl", jsonl, "application/x-ndjson")},
    )
    assert imported.status_code == 201, imported.text
    assert imported.json()["imported"] == 2
    assert imported.json()["seeds"][0]["source"] == "import-jsonl"

    csv_data = (
        '\ufeffstate,labels,language\n"ticket: CSV seed","{""team"": ""billing""}",zh\n'
    ).encode()
    imported_csv = client.post(
        f"/api/v1/projects/{project_id}/seeds/import",
        files={"file": ("seeds.csv", csv_data, "text/csv")},
    )
    assert imported_csv.status_code == 201, imported_csv.text
    assert imported_csv.json()["imported"] == 1
    assert imported_csv.json()["seeds"][0]["state"] == {"text": "ticket: CSV seed"}

    invalid = client.post(
        f"/api/v1/projects/{project_id}/seeds/import",
        files={
            "file": (
                "bad.jsonl",
                b'{"state":{"ticket":"x"},"labels":{"unknown":"x"}}\n',
                "application/x-ndjson",
            )
        },
    )
    assert invalid.status_code == 422
    assert "unknown question keys" in invalid.json()["error"]["message"]


def test_playground_validation(client: TestClient, project_factory) -> None:
    missing_project = client.post(
        "/api/v1/playground/run",
        json={"projectId": "missing", "model": "laya-base", "state": {"ticket": "x"}},
    )
    assert missing_project.status_code == 404

    empty_project = client.post(
        "/api/v1/projects",
        json={"name": "Empty", "domain": "No schema", "languages": ["en"]},
    )
    assert empty_project.status_code == 201, empty_project.text
    no_questions = client.post(
        "/api/v1/playground/run",
        json={
            "projectId": empty_project.json()["id"],
            "model": "laya-base",
            "state": {"ticket": "x"},
        },
    )
    assert no_questions.status_code == 422
    assert "at least one question" in no_questions.json()["error"]["message"]

    project_id, _, _ = project_factory()
    empty_state = client.post(
        "/api/v1/playground/run",
        json={"projectId": project_id, "model": "laya-base", "state": {}},
    )
    assert empty_state.status_code == 422

    unsupported = client.post(
        "/api/v1/playground/run",
        json={"projectId": project_id, "model": "unknown", "state": {"ticket": "x"}},
    )
    assert unsupported.status_code == 422

    runtime_missing = client.post(
        "/api/v1/playground/run",
        json={"projectId": project_id, "model": "laya-base", "state": {"ticket": "x"}},
    )
    assert runtime_missing.status_code == 400
    assert "runtime" in runtime_missing.json()["error"]["message"].lower()

    custom_questions = client.post(
        "/api/v1/playground/run",
        json={
            "model": "laya-base",
            "state": "A hamburger is a sandwich.",
            "questions": [
                {
                    "key": "is_sandwich",
                    "type": "noul",
                    "instructions": "Is a hamburger a sandwich?",
                    "criteria": {"true": "Fits the definition", "false": "Does not fit"},
                }
            ],
        },
    )
    assert custom_questions.status_code == 400
    assert "runtime" in custom_questions.json()["error"]["message"].lower()

    missing_options = client.post(
        "/api/v1/playground/run",
        json={
            "model": "laya-base",
            "state": "x",
            "questions": [{"key": "color", "type": "choice", "instructions": "Which?"}],
        },
    )
    assert missing_options.status_code == 422
    assert "needs options" in missing_options.json()["error"]["message"]


def test_generation_preview_includes_advanced_options(client: TestClient, project_factory) -> None:
    project_id, _, _ = project_factory()
    defaults = client.get(f"/api/v1/projects/{project_id}/generation-prompt-defaults")
    assert defaults.status_code == 200, defaults.text
    assert "{{schema_json}}" in defaults.json()["user"]
    assert "custom_prompt" in defaults.json()["placeholders"]

    response = client.post(
        f"/api/v1/projects/{project_id}/generation-preview",
        json={
            "count": 5,
            "languages": ["en"],
            "teacher": "none",
            "customPrompt": "Prefer short, realistic support tickets.",
            "systemPromptTemplate": "System for {{project_name}} in {{language}}.",
            "userPromptTemplate": (
                "Generate {{count}} items. Schema: {{schema_json}}. "
                "{{default_user}} Extra: {{custom_prompt}}"
            ),
            "llm": {"temperature": 0.2, "thinkBudget": 512, "thinkLevel": "medium"},
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["batchSize"] == 5
    assert data["body"]["temperature"] == 0.2
    assert data["body"]["reasoning"]["max_tokens"] == 512
    assert data["body"]["reasoning_effort"] == "medium"
    assert data["body"]["messages"][0]["content"].startswith("System for Support")
    assert "Generate 5 items." in data["body"]["messages"][1]["content"]
    assert "Prefer short, realistic support tickets." in data["body"]["messages"][1]["content"]
    assert data["body"]["response_format"] == {"type": "json_object"}

    unknown = client.post(
        f"/api/v1/projects/{project_id}/generation-preview",
        json={
            "count": 5,
            "teacher": "none",
            "userPromptTemplate": "Generate {{unknown_placeholder}}",
        },
    )
    assert unknown.status_code == 422
    assert "Unknown prompt placeholders" in unknown.json()["error"]["message"]


def test_nvidia_gpu_detection(monkeypatch) -> None:
    from app.services import gpu

    monkeypatch.setattr(
        gpu,
        "_run",
        lambda command: "NVIDIA GeForce RTX 4090, 24564, 1024, 580.65, 8.9",
    )
    devices = gpu.detect_gpu_devices()
    assert devices[0]["backend"] == "cuda"
    assert devices[0]["name"] == "NVIDIA GeForce RTX 4090"
    assert devices[0]["memory_total_mb"] == 24564
    assert devices[0]["memory_used_mb"] == 1024
    assert devices[0]["compute_capability"] == "8.9"


def test_rocm_gpu_detection(monkeypatch) -> None:
    from app.services import gpu

    monkeypatch.setattr(gpu, "_nvidia_devices", lambda: [])
    payload = json.dumps(
        {
            "card0": {
                "VRAM Total Memory (B)": str(2 * gpu.MIB),
                "VRAM Total Used Memory (B)": str(gpu.MIB // 2),
                "Card Series": "AMD Radeon Graphics",
                "Card Vendor": "AMD",
                "GFX Version": "gfx1151",
            },
            "system": {"Driver version": "7.0.0"},
        }
    )
    monkeypatch.setattr(gpu, "_run", lambda command: payload)
    devices = gpu.detect_gpu_devices()
    assert devices[0]["backend"] == "rocm"
    assert devices[0]["memory_total_mb"] == 2
    assert devices[0]["compute_capability"] == "gfx1151"


def test_training_charts_for_gliner_and_fit(
    client: TestClient,
    project_factory,
    tmp_path: Path,
) -> None:
    project_id, _, _ = project_factory()
    _accept_seed(client, project_id, "Training chart sample")
    snapshot = client.post(f"/api/v1/projects/{project_id}/datasets")
    assert snapshot.status_code == 201, snapshot.text
    snapshot_id = snapshot.json()["id"]

    gliner_root = tmp_path / "gliner-job"
    (gliner_root / "gliner").mkdir(parents=True)
    (gliner_root / "train.log").write_text("Training: loss=1.0, lr=1e-5\\n", encoding="utf-8")
    (gliner_root / "gliner" / "gliner_train_report.json").write_text(
        json.dumps(
            {
                "total_steps": 1,
                "total_epochs": 1,
                "train_metrics_history": [
                    {
                        "loss": 1.0,
                        "classification_loss": 0.9,
                        "structure_loss": 0.0,
                        "count_loss": 0.0,
                        "learning_rate": 1e-5,
                        "epoch": 1.0,
                        "step": 1,
                        "throughput": 10.0,
                    }
                ],
                "eval_metrics_history": [{"eval_loss": 0.8, "step": 1, "epoch": 1.0}],
            }
        ),
        encoding="utf-8",
    )

    fit_root = tmp_path / "fit-job"
    (fit_root / "calibration").mkdir(parents=True)
    (fit_root / "calibration" / "fit_report.json").write_text(
        json.dumps(
            {
                "heads": {
                    "team": {
                        "fitted": True,
                        "examples": 10,
                        "cv_accuracy": 0.9,
                        "engine_accuracy": 0.8,
                        "chance": 0.33,
                        "used_by_auto": True,
                    }
                },
                "calibration": {
                    "questions": {
                        "team": {
                            "temperature": 1.0,
                            "ece_before": 0.2,
                            "ece_after": 0.1,
                        }
                    }
                },
                "n_rows": 10,
                "n_fit": 8,
                "n_calibrate": 2,
                "serving": ["team"],
                "kept": ["team"],
            }
        ),
        encoding="utf-8",
    )

    db = SessionLocal()
    try:
        gliner_job = TrainingJob(
            project_id=project_id,
            snapshot_id=snapshot_id,
            target="gliner",
            mode="finetune",
            device="cpu",
            config={},
            status="completed",
            stage="completed",
            log_path=str(gliner_root / "train.log"),
        )
        fit_job = TrainingJob(
            project_id=project_id,
            snapshot_id=snapshot_id,
            target="laya",
            mode="fit",
            device="cpu",
            config={},
            status="completed",
            stage="completed",
            log_path=str(fit_root / "train.log"),
        )
        db.add_all([gliner_job, fit_job])
        db.commit()
        db.refresh(gliner_job)
        db.refresh(fit_job)
        gliner_id = gliner_job.id
        fit_id = fit_job.id
    finally:
        db.close()

    gliner_charts = client.get(f"/api/v1/training-jobs/{gliner_id}/charts")
    assert gliner_charts.status_code == 200, gliner_charts.text
    keys = {series["key"] for series in gliner_charts.json()["series"]}
    assert {"loss", "learning_rate", "classification_loss", "throughput", "eval_loss"} <= keys

    fit_charts = client.get(f"/api/v1/training-jobs/{fit_id}/charts")
    assert fit_charts.status_code == 200, fit_charts.text
    fit_body = fit_charts.json()
    assert fit_body["heads"][0]["key"] == "team"
    assert fit_body["heads"][0]["cvAccuracy"] == 0.9
    assert fit_body["heads"][0]["eceBefore"] == 0.2
    assert any("Loss/LR" in warning for warning in fit_body["warnings"])


def test_laya_training_charts_read_metrics(
    client: TestClient,
    project_factory,
    tmp_path: Path,
) -> None:
    project_id, _, _ = project_factory()
    _accept_seed(client, project_id, "Laya metrics sample")
    snapshot = client.post(f"/api/v1/projects/{project_id}/datasets")
    assert snapshot.status_code == 201, snapshot.text
    root = tmp_path / "laya-job"
    (root / "checkpoint").mkdir(parents=True)
    (root / "train.log").write_text(
        "epoch 1/2 step 10 loss 0.5000\nepoch 2/2 step 10 loss 0.4000\n",
        encoding="utf-8",
    )
    (root / "checkpoint" / "laya_metrics.json").write_text(
        json.dumps(
            {
                "epoch_loss": [0.5, 0.4],
                "learning_rate": [
                    {"step": 1, "values": [2.5e-5, 1e-4]},
                    {"step": 2, "values": [1.3e-5, 5e-5]},
                ],
            }
        ),
        encoding="utf-8",
    )
    (root / "checkpoint" / "train_report.json").write_text(
        json.dumps(
            {"before": {"loss": 1.0, "accuracy": 0.5}, "after": {"loss": 0.8, "accuracy": 0.7}}
        ),
        encoding="utf-8",
    )

    db = SessionLocal()
    try:
        job = TrainingJob(
            project_id=project_id,
            snapshot_id=snapshot.json()["id"],
            target="laya",
            mode="finetune",
            device="cpu",
            config={},
            status="completed",
            stage="completed",
            log_path=str(root / "train.log"),
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        job_id = job.id
    finally:
        db.close()

    charts = client.get(f"/api/v1/training-jobs/{job_id}/charts")
    assert charts.status_code == 200, charts.text
    series = {item["key"]: item["points"] for item in charts.json()["series"]}
    assert len(series["loss"]) == 2
    assert len(series["loss_step"]) == 2
    assert len(series["learning_rate_encoder"]) == 2
    assert len(series["learning_rate_head"]) == 2
