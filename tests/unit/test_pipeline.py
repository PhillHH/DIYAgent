"""Unit-Tests fuer die asynchrone Pipeline-Logik."""

from __future__ import annotations

import pytest

from orchestrator.pipeline import SettingsBundle, run_job
from orchestrator.status import get_status, reset_statuses


@pytest.mark.asyncio
async def test_run_job_rejects_non_diy_query() -> None:
    reset_statuses()

    job_id = "job-non-diy"
    await run_job(job_id, "Aktienkurs Apple", "user@example.com", SettingsBundle())
    status = get_status(job_id)

    assert status["phase"] == "rejected"
    assert "Heimwerker" in (status["detail"] or "")


@pytest.mark.asyncio
async def test_run_job_records_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    reset_statuses()

    async def fake_plan(query, settings):  # type: ignore[unused-argument]
        from agents.schemas import WebSearchItem, WebSearchPlan

        return WebSearchPlan(
            searches=[WebSearchItem(reason="Test", query="Test")]
        )

    async def failing_search(*args, **kwargs):  # type: ignore[unused-argument]
        raise RuntimeError("Netzwerkfehler")

    monkeypatch.setattr("orchestrator.pipeline.plan_searches", fake_plan)
    monkeypatch.setattr("orchestrator.pipeline.perform_searches", failing_search)

    job_id = "job-error"
    await run_job(job_id, "Regal bauen", "user@example.com", SettingsBundle())
    status = get_status(job_id)

    assert status["phase"] == "error"
    assert "Netzwerkfehler" in (status["detail"] or "")

