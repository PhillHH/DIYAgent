"""Integrationstest fuer den orchestrierten Job-Flow."""

from __future__ import annotations

import pytest

from agents.schemas import ReportData, WebSearchItem, WebSearchPlan, SearchPhase
from models.report_payload import (
    FAQItem,
    NarrativeSection,
    ReportMeta,
    ReportPayload,
    ShoppingItem,
    ShoppingList,
    StepDetail,
    StepsSection,
    TimeCostRow,
    TimeCostSection,
)
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
                WebSearchItem(reason=SearchPhase.MATERIAL_WERKZEUGE, query="Materialien fuer Regal"),
                WebSearchItem(reason=SearchPhase.VORBEREITUNG_PLANUNG, query="Werkzeug fuer Regal"),
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
        payload = ReportPayload(
            title="Bericht",
            teaser="Kurze Zusammenfassung",
            meta=ReportMeta(difficulty="Anfänger", duration="4–6 h", budget="120–180 €"),
            toc=[],
            preparation=NarrativeSection(heading="Vorbereitung", paragraphs=summaries, bullets=[], note=None),
            shopping_list=ShoppingList(
                items=[
                    ShoppingItem(
                        category="Material",
                        product="Bauhaus Test",
                        quantity="1",
                        rationale="Hauptprodukt",
                        price="ca. 10 €",
                        url="https://www.bauhaus.info/test",
                    )
                ]
            ),
            step_by_step=StepsSection(heading="Schritt-für-Schritt", steps=[StepDetail(title="Montage", bullets=[], check="OK")]),
            quality_safety=NarrativeSection(heading="Qualität & Sicherheit", paragraphs=[], bullets=[], note=None),
            time_cost=TimeCostSection(heading="Zeit & Kosten", rows=[TimeCostRow(work_package="Test", duration="1 h", cost="10 €")]),
            options_upgrades=None,
            maintenance=None,
            faq=[FAQItem(question="Frage", answer="Antwort") for _ in range(5)],
            followups=["Als Nächstes: Kontrolle" for _ in range(4)],
            search_summary=None,
        )
        return ReportData(
            short_summary="Kurze Zusammenfassung",
            markdown_report="# Bericht\n\nDIY-Inhalt",
            followup_questions=payload.followups,
            payload=payload,
        )

    async def fake_email(*args, **kwargs):  # type: ignore[unused-argument]
        return {"status": "sent"}

    async def fake_input_guard(query, settings):  # type: ignore[unused-argument]
        return InputGuardResult(category="DIY", reasons=["Test"])

    async def fake_output_guard(query, report_md, settings):  # type: ignore[unused-argument]
        return OutputGuardResult(allowed=True, issues=[], category="DIY")

    async def fake_enrichment(*args, **kwargs):  # type: ignore[unused-argument]
        return []

    monkeypatch.setattr("orchestrator.pipeline.classify_query_llm", fake_input_guard)
    monkeypatch.setattr("orchestrator.pipeline.audit_report_llm", fake_output_guard)
    monkeypatch.setattr("orchestrator.pipeline.plan_searches", fake_plan)
    monkeypatch.setattr("orchestrator.pipeline.perform_searches", fake_search)
    monkeypatch.setattr("orchestrator.pipeline.perform_product_enrichment", fake_enrichment)
    monkeypatch.setattr("orchestrator.pipeline.write_report", fake_writer)
    monkeypatch.setattr("orchestrator.pipeline.send_email", fake_email)

    job_id = "integration-job"
    await run_job(job_id, "Regal im Keller bauen", "user@example.com", SettingsBundle())

    status = get_status(job_id)
    assert status["phase"] == "done", status
    assert status.get("payload", {}).get("report_payload")

