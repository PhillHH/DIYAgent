"""Tests fuer Writer ohne Platzhalter-Links."""

from __future__ import annotations

import json

import pytest

from agents.model_settings import DEFAULT_WRITER
from agents.writer import write_report


@pytest.mark.asyncio
async def test_writer_without_products_omits_links(monkeypatch: pytest.MonkeyPatch) -> None:
    query = "Regal bauen"
    search_results = ["Kurze Vorbereitung"]

    async def fake_invoke(messages, settings, schema=None):  # type: ignore[unused-argument]
        return json.dumps(
            {
                "short_summary": "Kurz",
                "report_payload": {
                    "title": "Projekt",
                    "teaser": "Start in das Projekt.",
                    "meta": {
                        "difficulty": "Anfänger",
                        "duration": "4–6 h",
                        "budget": "120–180 €",
                        "region": "DE",
                    },
                    "toc": [],
                    "preparation": {
                        "heading": "Vorbereitung",
                        "paragraphs": ["Text"],
                        "bullets": [],
                        "note": None,
                    },
                    "shopping_list": {
                        "heading": "Einkaufsliste (Bauhaus-Links)",
                        "intro": None,
                        "items": [],
                        "empty_hint": "Keine geprüften Bauhaus-Produkte verfügbar.",
                    },
                    "step_by_step": {
                        "heading": "Schritt-für-Schritt",
                        "steps": [
                            {
                                "title": "Schritt",
                                "bullets": ["Aktion"],
                                "check": "Test",
                                "tip": None,
                                "warning": None,
                            }
                        ],
                    },
                    "quality_safety": {
                        "heading": "Qualität & Sicherheit",
                        "paragraphs": ["Text"],
                        "bullets": [],
                        "note": None,
                    },
                    "time_cost": {
                        "heading": "Zeit & Kosten",
                        "rows": [
                            {
                                "work_package": "Test",
                                "duration": "1 h",
                                "cost": "10 €",
                                "buffer": None,
                            }
                        ],
                        "summary": None,
                    },
                    "options_upgrades": None,
                    "maintenance": None,
                    "faq": [
                        {"question": "Frage?", "answer": "Antwort."},
                        {"question": "Frage 2?", "answer": "Antwort."},
                        {"question": "Frage 3?", "answer": "Antwort."},
                        {"question": "Frage 4?", "answer": "Antwort."},
                        {"question": "Frage 5?", "answer": "Antwort."},
                    ],
                    "followups": [
                        "Als Nächstes: Planung abgleichen",
                        "Als Nächstes: Materialliste prüfen",
                        "Als Nächstes: Arbeitsfläche vorbereiten",
                        "Als Nächstes: Sicherheitscheck durchführen",
                    ],
                    "search_summary": None,
                },
                "followup_questions": [
                    "Als Nächstes: Planung abgleichen",
                    "Als Nächstes: Materialliste prüfen",
                    "Als Nächstes: Arbeitsfläche vorbereiten",
                    "Als Nächstes: Sicherheitscheck durchführen",
                ],
            }
        )

    monkeypatch.setattr("agents.writer._invoke_writer_model", fake_invoke)

    report = await write_report(query, search_results, DEFAULT_WRITER, product_results=[])

    assert report.payload is not None
    assert report.payload.shopping_list.items == []
    einkauf_index = report.markdown_report.lower().find("## einkaufsliste (bauhaus-links)")
    assert einkauf_index != -1
    einkauf_section = report.markdown_report[einkauf_index:]
    assert "http" not in einkauf_section

