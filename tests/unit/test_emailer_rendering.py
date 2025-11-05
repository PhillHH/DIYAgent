"""Tests fuer die Premium-E-Mail-Ausgabe."""

from __future__ import annotations

import types

import pytest

from agents.emailer import _render_structured_email, send_email
from agents.schemas import ReportData
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


def test_emailer_rendering_contains_toc_and_tables() -> None:
    payload = ReportPayload(
        title="Premium Projekt",
        teaser="Kurze Beschreibung.",
        meta=ReportMeta(difficulty="Fortgeschritten", duration="6–8 h", budget="250–320 €"),
        toc=[],
        preparation=NarrativeSection(heading="Abschnitt A", paragraphs=["Text."], bullets=[], note=None),
        shopping_list=ShoppingList(
            items=[
                ShoppingItem(
                    category="Material",
                    product="Holzbrett",
                    quantity="5",
                    rationale="Regalbrett",
                    price="12 €",
                    url=None,
                )
            ]
        ),
        step_by_step=StepsSection(
            heading="Abschnitt B",
            steps=[StepDetail(title="Unterpunkt", bullets=["Schritt"], check="Prüfen")],
        ),
        quality_safety=NarrativeSection(heading="Qualität", paragraphs=["Sicherheitscheck."], bullets=[], note=None),
        time_cost=TimeCostSection(
            heading="Zeit & Kosten",
            rows=[TimeCostRow(work_package="Vorbereitung", duration="2 h", cost="60 €")],
        ),
        options_upgrades=None,
        maintenance=None,
        faq=[FAQItem(question="Frage", answer="Antwort") for _ in range(5)],
        followups=["Als Nächstes: Kontrolle" for _ in range(4)],
        search_summary=None,
    )
    report = ReportData(short_summary="Kurz", markdown_report="# Platzhalter", followup_questions=payload.followups, payload=payload)
    html, subject, meta = _render_structured_email(report, payload, brand=None, meta_override=None)
    assert "nav class=\"toc\"" in html
    assert "class=\"table product-table\"" in html
    assert "class=\"step-grid\"" in html
    assert '<div class="step-card">' in html
    assert '<a id="abschnitt-b"' in html
    assert isinstance(subject, str)
    assert isinstance(meta, dict)


@pytest.mark.asyncio
async def test_email_size_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    large_markdown = "# Titel\n## Material\nLaminat verlegen Anleitung.\n" + "DIY Arbeiten vorbereiten.\n" * 6000
    report = ReportData(short_summary="Kurz", markdown_report=large_markdown, followup_questions=[])

    async def fake_post(payload):  # type: ignore[unused-argument]
        return types.SimpleNamespace(status_code=202, text="")

    monkeypatch.setattr("agents.emailer._post_sendgrid", fake_post)
    monkeypatch.setattr("agents.emailer.SENDGRID_API_KEY", "key")
    monkeypatch.setattr("agents.emailer.FROM_EMAIL", "sender@example.com")

    result = await send_email(report, "user@example.com")
    assert result["status"] == "sent"
    assert result["status_code"] == 202

