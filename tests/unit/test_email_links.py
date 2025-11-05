"""Tests fuer die Einkaufsliste im E-Mail-Renderer."""

from __future__ import annotations

from agents.emailer import _render_structured_email
from agents.schemas import ReportData
from models.report_payload import (
    ReportMeta,
    ReportPayload,
    ShoppingItem,
    ShoppingList,
    StepsSection,
    StepDetail,
    NarrativeSection,
    TimeCostSection,
    TimeCostRow,
    FAQItem,
)


def test_email_einkaufsliste_contains_only_bauhaus_links() -> None:
    payload = ReportPayload(
        title="Projekt",
        teaser="Kurzer Überblick.",
        meta=ReportMeta(difficulty="Fortgeschritten", duration="6–8 h", budget="250–320 €", region="AT"),
        toc=[],
        preparation=NarrativeSection(heading="Vorbereitung", paragraphs=[], bullets=[], note=None),
        shopping_list=ShoppingList(
            items=[
                ShoppingItem(
                    category="Material",
                    product="Artikel 1",
                    quantity="1",
                    rationale="Hauptprodukt",
                    price="ca. 10 €",
                    url="https://www.bauhaus.info/a?utm=123",
                ),
                ShoppingItem(
                    category="Zubehör",
                    product="Artikel 2",
                    quantity="2",
                    rationale="Ergänzung",
                    price="ca. 20 €",
                    url="https://www.bauhaus.de/b#frag",
                ),
                ShoppingItem(
                    category="Werkzeuge",
                    product="Artikel 3",
                    quantity="1",
                    rationale="Hinweis",
                    price="ca. 30 €",
                    url="https://www.bauhaus.at/c?ref=123",
                ),
            ]
        ),
        step_by_step=StepsSection(heading="Schritt-für-Schritt", steps=[StepDetail(title="Test", bullets=[], check="OK")]),
        quality_safety=NarrativeSection(heading="Qualität & Sicherheit", paragraphs=[], bullets=[], note=None),
        time_cost=TimeCostSection(heading="Zeit & Kosten", rows=[TimeCostRow(work_package="Test", duration="1 h", cost="5 €")]),
        options_upgrades=None,
        maintenance=None,
        faq=[FAQItem(question="Frage", answer="Antwort") for _ in range(5)],
        followups=["Als Nächstes: Test" for _ in range(4)],
        search_summary=None,
    )

    report = ReportData(
        short_summary="Kurz",
        markdown_report="# Projekt",
        followup_questions=payload.followups,
        payload=payload,
    )

    html, _, _ = _render_structured_email(report, report.payload, brand=None, meta_override=None)

    assert html.count("https://www.bauhaus") >= 3
    assert "utm=" not in html
    assert "mail.google.com" not in html
    assert html.count("<tr>") >= 6

