from __future__ import annotations

import os
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

TEST_ROOT = Path(tempfile.mkdtemp(prefix="autolaya-tests-"))
os.environ["DATA_DIR"] = str(TEST_ROOT / "data")
os.environ["DATABASE_URL"] = f"sqlite:///{(TEST_ROOT / 'test.db').as_posix()}"
os.environ["LLM_API_KEY"] = ""
os.environ["TYPESAFE_API_KEY"] = ""
os.environ["OPENROUTER_API_KEY"] = ""
os.environ["JOB_WORKER_ENABLED"] = "0"

from app.core.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as test_client:
        yield test_client


def create_project(client: TestClient, name: str = "Support") -> tuple[str, str, str]:
    project = client.post(
        "/api/v1/projects",
        json={"name": name, "domain": "Support tickets", "languages": ["en", "zh"]},
    )
    assert project.status_code == 201, project.text
    project_id = project.json()["id"]

    team = client.post(
        f"/api/v1/projects/{project_id}/questions",
        json={
            "key": "team",
            "type": "choice",
            "instructions": "Which team should handle this?",
            "criteria": {
                "billing": "Refunds and payments",
                "technical": "Bugs and outages",
                "sales": "Pricing and quotes",
            },
        },
    )
    assert team.status_code == 201, team.text

    urgent = client.post(
        f"/api/v1/projects/{project_id}/questions",
        json={
            "key": "urgent",
            "type": "noul",
            "instructions": "Does this need attention today?",
        },
    )
    assert urgent.status_code == 201, urgent.text
    return project_id, team.json()["id"], urgent.json()["id"]


@pytest.fixture()
def project_factory(client: TestClient):
    def factory(name: str = "Support") -> tuple[str, str, str]:
        return create_project(client, name)

    return factory
