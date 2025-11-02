"""Stellt sicher, dass Produktergebnisse durch die Pipeline gereicht werden."""

from __future__ import annotations

import pytest

from agents.schemas import ReportData, WebSearchItem, WebSearchPlan
from guards.schemas import InputGuardResult, OutputGuardResult
from models.types import ProductItem
from orchestrator.pipeline import SettingsBundle, run_job
from orchestrator.status import get_status, reset_statuses


@pytest.mark.asyncio
async def test_pipeline_propagates_product_results(monkeypatch: pytest.MonkeyPatch) -> None:
    reset_statuses()

    product = ProductItem(
        title="Bauhaus Testprodukt",
        url="https://www.bauhaus.info/produkt",
        note="Hinweis",
        price_text="ca. 9,99 €",
    )

    async def fake_plan(query, settings):  # type: ignore[unused-argument]
        return WebSearchPlan(searches=[WebSearchItem(reason="Allgemein", query="Test")])

    async def fake_search(plan, settings, *, user_query, category):  # type: ignore[unused-argument]
        return ["Zusammenfassung"], []

    async def fake_product_enrichment(user_query, search_results, settings):  # type: ignore[unused-argument]
        assert search_results == ["Zusammenfassung"]
        return [product]

    async def fake_writer(query, summaries, settings, category=None, product_results=None):  # type: ignore[unused-argument]
        assert product_results == [product]
        return ReportData(
            short_summary="Kurz",
            markdown_report="# Report\n\n## Vorbereitung\nText",
            followup_questions=["Frage 1", "Frage 2", "Frage 3", "Frage 4"],
        )

    async def fake_input_guard(query, settings):  # type: ignore[unused-argument]
        return InputGuardResult(category="DIY", reasons=["ok"])

    async def fake_output_guard(query, report_md, settings):  # type: ignore[unused-argument]
        return OutputGuardResult(allowed=True, issues=[], category="DIY")

    async def fake_email(report, to_email, product_results=None, brand=None, meta=None):  # type: ignore[unused-argument]
        assert product_results == [product]
        return {"status": "sent", "status_code": 202, "links": [], "html_preview": ""}

    monkeypatch.setattr("orchestrator.pipeline.classify_query_llm", fake_input_guard)
    monkeypatch.setattr("orchestrator.pipeline.plan_searches", fake_plan)
    monkeypatch.setattr("orchestrator.pipeline.perform_searches", fake_search)
    monkeypatch.setattr("orchestrator.pipeline.perform_product_enrichment", fake_product_enrichment)
    monkeypatch.setattr("orchestrator.pipeline.write_report", fake_writer)
    monkeypatch.setattr("orchestrator.pipeline.audit_report_llm", fake_output_guard)
    monkeypatch.setattr("orchestrator.pipeline.send_email", fake_email)

    job_id = "product-pipeline"
    await run_job(job_id, "Regal bauen", "user@example.com", SettingsBundle())

    status = get_status(job_id)
    assert status["phase"] == "done"
    payload = status.get("payload") or {}
    assert payload.get("product_results") == [product.model_dump()]

