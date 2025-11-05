"""Unit-Tests fuer den Writer-Agenten."""

from __future__ import annotations

import json

import pytest

from agents.model_settings import DEFAULT_WRITER
from agents.writer import write_report


@pytest.mark.asyncio
async def test_writer_premium_length(monkeypatch: pytest.MonkeyPatch) -> None:
    query = "Wand streichen im Schlafzimmer"
    search_results = [
        "Vorbereitung: Untergrund reinigen, abkleben und Grundierung kontrollieren.",
        "Material: Abdeckfolie, Malerkrepp und hochwertige Wandfarbe bereitstellen.",
        "Durchfuehrung: In Bahnen streichen, etwaige Tropfen sofort entfernen und trocknen lassen.",
    ]

    report_payload = {
        "title": "Wand streichen wie ein Profi",
        "teaser": "Mit sauberer Vorbereitung gelingt dein Anstrich in einem Tag.",
        "meta": {
            "difficulty": "Anfänger",
            "duration": "2–4 h",
            "budget": "150–220 €",
            "region": "DE",
        },
        "preparation": {
            "heading": "Vorbereitung",
            "paragraphs": [
                "Räume das Zimmer und decke Böden sowie Möbel mit Folien ab.",
            ],
            "bullets": ["Werkzeuge kontrollieren", "Farbprobe anlegen"],
            "note": None,
        },
        "shopping_list": {
            "heading": "Einkaufsliste (Bauhaus-Links)",
            "intro": "Alle Produkte stammen aus geprüften Bauhaus-Quellen.",
            "items": [
                {
                    "category": "Farbe",
                    "product": "Premium-Wandfarbe weiss",
                    "quantity": "2 Eimer",
                    "rationale": "Deckende Innenfarbe für 25 m²",
                    "price": "ca. 89 €",
                    "url": None,
                }
            ],
            "empty_hint": "Keine geprüften Bauhaus-Produkte verfügbar.",
        },
        "step_by_step": {
            "heading": "Schritt-für-Schritt",
            "steps": [
                {
                    "title": "Untergrund prüfen",
                    "bullets": ["Lose Teile entfernen", "Risse spachteln"],
                    "check": "Wände glatt und trocken",
                    "tip": "Nutze den Handrücken zum Feuchte-Test.",
                    "warning": None,
                },
                {
                    "title": "Abkleben & Grundieren",
                    "bullets": ["Sockelleisten abkleben", "Tiefgrund auftragen"],
                    "check": "Grundierung gleichmäßig verteilt",
                    "tip": None,
                    "warning": "Nicht bei unter 10 °C arbeiten.",
                },
            ],
        },
        "quality_safety": {
            "heading": "Qualität & Sicherheit",
            "paragraphs": ["Lüfte regelmäßig und nutze geeignete Schutzkleidung."],
            "bullets": ["PSA tragen", "Leiter sichern"],
            "note": None,
        },
        "time_cost": {
            "heading": "Zeit & Kosten",
            "rows": [
                {
                    "work_package": "Vorbereitung",
                    "duration": "1–2 h",
                    "cost": "30 €",
                    "buffer": "0.5 h",
                },
                {
                    "work_package": "Anstrich",
                    "duration": "2 h",
                    "cost": "120 €",
                    "buffer": "50 €",
                },
            ],
            "summary": "Plane einen zusätzlichen Tag Trocknungsreserve ein.",
        },
        "options_upgrades": {
            "heading": "Optionen & Upgrades",
            "paragraphs": [],
            "bullets": ["Akzentwand mit Farbverlauf", "LED-Lichtleiste montieren"],
            "note": None,
        },
        "maintenance": {
            "heading": "Pflege & Wartung",
            "paragraphs": ["Staubfrei halten und Flecken zeitnah reinigen."],
            "bullets": [],
            "note": None,
        },
        "faq": [
            {"question": "Wie lange trocknet die Farbe?", "answer": "Etwa 12 Stunden bei 20 °C."},
            {"question": "Welche Rolle nutzen?", "answer": "Kurzflorige Rollen für glatte Wände."},
            {"question": "Muss ich grundieren?", "answer": "Ja, bei stark saugenden Untergründen."},
            {"question": "Wie oft streichen?", "answer": "Zwei gleichmäßige Anstriche genügen."},
            {"question": "Welche Schutzkleidung brauche ich?", "answer": "Handschuhe, Schutzbrille und Atemschutz."},
        ],
        "followups": [
            "Materialliste final abstimmen",
            "Trocknungszeit im Kalender blocken",
            "Abdeckmaterial besorgen",
            "Raumbelegung für den Anstrich planen",
        ],
        "search_summary": "Fokus auf emissionsarme Farbe und saubere Vorbereitung.",
    }

    async def fake_invoke(messages, settings, schema=None):  # type: ignore[unused-argument]
        return json.dumps(
            {
                "short_summary": "Sehr lange Zusammenfassung.",
                "report_payload": report_payload,
                "followup_questions": [
                    "Materialliste final abstimmen",
                    "Trocknungszeit im Kalender blocken",
                    "Abdeckmaterial besorgen",
                    "Raumbelegung für den Anstrich planen",
                ],
            }
        )

    monkeypatch.setattr("agents.writer._invoke_writer_model", fake_invoke)

    report = await write_report(query, search_results, DEFAULT_WRITER)

    assert report.payload is not None
    assert report.payload.meta.duration == "2–4 h"
    assert "## Einkaufsliste (Bauhaus-Links)" in report.markdown_report
    assert "| Schritt | Handlung | Prüfkriterium |" in report.markdown_report
    assert "| Schritt 1" in report.markdown_report
    assert "| Schritt 2" in report.markdown_report
    assert "- [Als Nächstes](#als-naechstes)" in report.markdown_report
    assert report.followup_questions and report.followup_questions[0].startswith("Als Nächstes")


@pytest.mark.asyncio
async def test_writer_rejects_non_diy(monkeypatch: pytest.MonkeyPatch) -> None:
    query = "Aktien kaufen"
    search_results = ["Einsteiger sollten sich ueber Brokergebuehren informieren."]

    async def fake_invoke(messages, settings, schema=None):  # type: ignore[unused-argument]
        return json.dumps(
            {
                "short_summary": "Finanzanalyse",
                "markdown_report": "# Aktien",
                "followup_questions": ["Frage"],
            }
        )

    monkeypatch.setattr("agents.writer._invoke_writer_model", fake_invoke)

    report = await write_report(query, search_results, DEFAULT_WRITER, category="KI_CONTROL")
    assert report.markdown_report.startswith("# Aktien")

