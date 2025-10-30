"""Integrationstest fuer den orchestrierten Job-Flow."""

from __future__ import annotations

import pytest

from agents.schemas import ReportData, WebSearchItem, WebSearchPlan
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
        return [
            "Materialliste zusammenstellen",
            "Werkzeuge vorbereiten",
        ]

    async def fake_writer(query, summaries, settings):  # type: ignore[unused-argument]
        return ReportData(
            short_summary="Kurze Zusammenfassung",
            markdown_report="# Bericht\n\nDIY-Inhalt",
            followup_questions=["Frage 1", "Frage 2", "Frage 3"],
        )

    async def fake_email(*args, **kwargs):  # type: ignore[unused-argument]
        return {"status": "sent"}

    monkeypatch.setattr("orchestrator.pipeline.plan_searches", fake_plan)
    monkeypatch.setattr("orchestrator.pipeline.perform_searches", fake_search)
    monkeypatch.setattr("orchestrator.pipeline.write_report", fake_writer)
    monkeypatch.setattr("orchestrator.pipeline.send_email", fake_email)

    job_id = "integration-job"
    await run_job(job_id, "Regal im Keller bauen", "user@example.com", SettingsBundle())

    status = get_status(job_id)
    assert status["phase"] == "done"

