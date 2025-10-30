"""Integrationstests fuer die FastAPI-Endpunkte."""

from __future__ import annotations

import time
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from api.main import app
from orchestrator.status import get_status, reset_statuses, set_status


@pytest.fixture(autouse=True)
def clear_status_store() -> None:
    reset_statuses()
    yield
    reset_statuses()


def test_api_start_and_status(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_run(job_id: str, query: str, email: str, settings_bundle) -> None:  # type: ignore[unused-argument]
        set_status(job_id, "done", None)

    monkeypatch.setattr("orchestrator.pipeline.run_job", fake_run)
    monkeypatch.setattr("api.main.run_job", fake_run)

    client = TestClient(app)

    response = client.post(
        "/start_research",
        json={"query": "Regal bauen", "email": "user@example.com"},
    )
    assert response.status_code == 200
    job_id = response.json()["job_id"]

    final_status = None
    for _ in range(10):
        status_response = client.get(f"/status/{job_id}")
        assert status_response.status_code == 200
        final_status = status_response.json()
        if final_status["phase"] == "done":
            break
        time.sleep(0.05)

    assert final_status is not None
    assert final_status["phase"] == "done"

