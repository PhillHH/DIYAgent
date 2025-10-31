"""Integrationstests fuer Guard-Pfade in der Pipeline."""

from __future__ import annotations

import pytest

from agents.schemas import ReportData, WebSearchItem, WebSearchPlan
from guards.schemas import InputGuardResult, OutputGuardResult
from orchestrator.pipeline import SettingsBundle, run_job
from orchestrator.status import get_status, reset_statuses


@pytest.mark.asyncio
async def test_pipeline_rejects_when_input_guard_rejects(monkeypatch: pytest.MonkeyPatch) -> None:
    reset_statuses()

    async def fake_input_guard(query, settings):  # type: ignore[unused-argument]
        return InputGuardResult(category="REJECT", reasons=["Testablehnung"])

    monkeypatch.setattr("orchestrator.pipeline.classify_query_llm", fake_input_guard)

    job_id = "guard-reject"
    await run_job(job_id, "Aktien heute kaufen?", "user@example.com", SettingsBundle())
    status = get_status(job_id)

    assert status["phase"] == "rejected"
    assert "Testablehnung" in (status["detail"] or "")


@pytest.mark.asyncio
async def test_pipeline_runs_through_for_diy(monkeypatch: pytest.MonkeyPatch) -> None:
    reset_statuses()

    async def fake_input_guard(query, settings):  # type: ignore[unused-argument]
        return InputGuardResult(category="DIY", reasons=["Test DIY"])

    async def fake_plan(query, settings):  # type: ignore[unused-argument]
        return WebSearchPlan(
            searches=[
                WebSearchItem(reason="Material", query="Material"),
                WebSearchItem(reason="Werkzeug", query="Werkzeug"),
            ]
        )

    async def fake_search(*args, **kwargs):  # type: ignore[unused-argument]
        return ["Materialliste", "Werkzeugliste"]

    async def fake_writer(query, summaries, settings, category=None):  # type: ignore[unused-argument]
        return ReportData(
            short_summary="Kurz",
            markdown_report="# Report\n\nDIY",
            followup_questions=["Frage 1", "Frage 2", "Frage 3", "Frage 4"],
        )

    async def fake_output_guard(query, report_md, settings):  # type: ignore[unused-argument]
        return OutputGuardResult(allowed=True, category="DIY", issues=[])

    async def fake_email(*args, **kwargs):  # type: ignore[unused-argument]
        return {"status": "sent"}

    monkeypatch.setattr("orchestrator.pipeline.classify_query_llm", fake_input_guard)
    monkeypatch.setattr("orchestrator.pipeline.plan_searches", fake_plan)
    monkeypatch.setattr("orchestrator.pipeline.perform_searches", fake_search)
    monkeypatch.setattr("orchestrator.pipeline.write_report", fake_writer)
    monkeypatch.setattr("orchestrator.pipeline.audit_report_llm", fake_output_guard)
    monkeypatch.setattr("orchestrator.pipeline.send_email", fake_email)

    job_id = "guard-diy"
    await run_job(job_id, "Regal bauen", "user@example.com", SettingsBundle())
    status = get_status(job_id)

    assert status["phase"] == "done"


@pytest.mark.asyncio
async def test_pipeline_runs_through_for_ki_control(monkeypatch: pytest.MonkeyPatch) -> None:
    reset_statuses()

    async def fake_input_guard(query, settings):  # type: ignore[unused-argument]
        return InputGuardResult(category="KI_CONTROL", reasons=["Meta-Thema"])

    async def fake_plan(query, settings):  # type: ignore[unused-argument]
        return WebSearchPlan(
            searches=[WebSearchItem(reason="Analyse", query="KI"), WebSearchItem(reason="Governance", query="Governance")]
        )

    async def fake_search(*args, **kwargs):  # type: ignore[unused-argument]
        return ["Analyse", "Governance"]

    async def fake_writer(query, summaries, settings, category=None):  # type: ignore[unused-argument]
        return ReportData(
            short_summary="Kurz",
            markdown_report="# KI Governance Report\n\n## Ziel & Kontext",
            followup_questions=["Frage 1", "Frage 2", "Frage 3", "Frage 4"],
        )

    async def fake_output_guard(query, report_md, settings):  # type: ignore[unused-argument]
        return OutputGuardResult(allowed=True, category="KI_CONTROL", issues=[])

    async def fake_email(*args, **kwargs):  # type: ignore[unused-argument]
        return {"status": "sent"}

    monkeypatch.setattr("orchestrator.pipeline.classify_query_llm", fake_input_guard)
    monkeypatch.setattr("orchestrator.pipeline.plan_searches", fake_plan)
    monkeypatch.setattr("orchestrator.pipeline.perform_searches", fake_search)
    monkeypatch.setattr("orchestrator.pipeline.write_report", fake_writer)
    monkeypatch.setattr("orchestrator.pipeline.audit_report_llm", fake_output_guard)
    monkeypatch.setattr("orchestrator.pipeline.send_email", fake_email)

    job_id = "guard-ki"
    await run_job(job_id, "KI-Agenten sicher steuern", "user@example.com", SettingsBundle())
    status = get_status(job_id)

    assert status["phase"] == "done"
