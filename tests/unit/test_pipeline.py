"""Unit-Tests fuer die asynchrone Pipeline-Logik."""

from __future__ import annotations

import pytest

from guards.schemas import InputGuardResult, OutputGuardResult
from orchestrator.pipeline import SettingsBundle, run_job
from orchestrator.status import get_status, reset_statuses
from agents.schemas import WebSearchPlan, WebSearchItem, SearchPhase


@pytest.mark.asyncio
async def test_run_job_rejects_non_diy_query(monkeypatch: pytest.MonkeyPatch) -> None:
    reset_statuses()

    async def fake_input_guard(query, settings):  # type: ignore[unused-argument]
        return InputGuardResult(category="REJECT", reasons=["Kein DIY-Scope"])

    monkeypatch.setattr("orchestrator.pipeline.classify_query_llm", fake_input_guard)

    job_id = "job-non-diy"
    await run_job(job_id, "Aktienkurs Apple", "user@example.com", SettingsBundle())
    status = get_status(job_id)

    assert status["phase"] == "rejected"
    assert "Kein zulässiger Scope" in (status["detail"] or "")


@pytest.mark.asyncio
async def test_run_job_records_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    reset_statuses()

    async def fake_plan(query, settings):  # type: ignore[unused-argument]
        return WebSearchPlan(
            searches=[
                WebSearchItem(
                    reason=SearchPhase.VORBEREITUNG_PLANUNG,
                    query="Test",
                )
            ]
        )

    async def failing_search(*args, **kwargs):  # type: ignore[unused-argument]
        raise RuntimeError("Netzwerkfehler")

    async def fake_input_guard(query, settings):  # type: ignore[unused-argument]
        return InputGuardResult(category="DIY", reasons=["Zulässig"])

    async def fake_output_guard(query, report_md, settings):  # type: ignore[unused-argument]
        return OutputGuardResult(allowed=True, issues=[], category="DIY")

    monkeypatch.setattr("orchestrator.pipeline.classify_query_llm", fake_input_guard)
    monkeypatch.setattr("orchestrator.pipeline.audit_report_llm", fake_output_guard)
    monkeypatch.setattr("orchestrator.pipeline.plan_searches", fake_plan)
    monkeypatch.setattr("orchestrator.pipeline.perform_searches", failing_search)

    job_id = "job-error"
    await run_job(job_id, "Regal bauen", "user@example.com", SettingsBundle())
    status = get_status(job_id)

    assert status["phase"] == "error"
    assert "Netzwerkfehler" in (status.get("detail") or "")

