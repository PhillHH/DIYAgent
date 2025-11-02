"""Integrationstest fuer den orchestrierten Job-Flow."""

from __future__ import annotations

import pytest

from agents.schemas import ReportData, WebSearchItem, WebSearchPlan
from models.types import ProductItem
from guards.schemas import InputGuardResult, OutputGuardResult
from orchestrator.pipeline import SettingsBundle, run_job
from orchestrator.status import get_status, reset_statuses


@pytest.mark.asyncio
async def test_run_job_completes(monkeypatch: pytest.MonkeyPatch) -> None:
    reset_statuses()

    async def fake_plan(query, settings):  # type: ignore[unused-argument]
        return WebSearchPlan(
            searches=[
                WebSearchItem(reason="Materialien", query="Materialien fuer Regal"),
                WebSearchItem(reason="Werkzeuge", query="Werkzeug fuer Regal"),
            ]
        )

    async def fake_search(*args, **kwargs):  # type: ignore[unused-argument]
        return (
            [
                "Materialliste zusammenstellen",
                "Werkzeuge vorbereiten",
            ],
            [
                ProductItem(
                    title="Bauhaus Test",
                    url="https://www.bauhaus.info/test",
                    note="",
                    price_text="ca. 10 €",
                )
            ],
        )

    async def fake_writer(query, summaries, settings, category=None, product_results=None):  # type: ignore[unused-argument]
        return ReportData(
            short_summary="Kurze Zusammenfassung",
            markdown_report="# Bericht\n\nDIY-Inhalt",
            followup_questions=["Frage 1", "Frage 2", "Frage 3"],
        )

    async def fake_email(*args, **kwargs):  # type: ignore[unused-argument]
        return {"status": "sent"}

    async def fake_input_guard(query, settings):  # type: ignore[unused-argument]
        return InputGuardResult(category="DIY", reasons=["Test"])

    async def fake_output_guard(query, report_md, settings):  # type: ignore[unused-argument]
        return OutputGuardResult(allowed=True, issues=[], category="DIY")

    monkeypatch.setattr("orchestrator.pipeline.classify_query_llm", fake_input_guard)
    monkeypatch.setattr("orchestrator.pipeline.audit_report_llm", fake_output_guard)
    monkeypatch.setattr("orchestrator.pipeline.plan_searches", fake_plan)
    monkeypatch.setattr("orchestrator.pipeline.perform_searches", fake_search)
    monkeypatch.setattr("orchestrator.pipeline.write_report", fake_writer)
    monkeypatch.setattr("orchestrator.pipeline.send_email", fake_email)

    job_id = "integration-job"
    await run_job(job_id, "Regal im Keller bauen", "user@example.com", SettingsBundle())

    status = get_status(job_id)
    assert status["phase"] == "done"

