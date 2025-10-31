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

    premium_sections = [
        "# Premium Projekt",
        "## Executive Summary",
        "## Projektueberblick und Voraussetzungen",
        "## Material & Werkzeuge",
        "| Position | Spezifikation | Menge | Stückpreis | Summe |",
        "## Schritt-fuer-Schritt-Anleitung",
        "## Zeit- & Kostenplan",
        "## Qualitätssicherung & typische Fehler",
        "## Sicherheit",
        "## Premium-Laminat",
        "## Pflege & Wartung",
        "## FAQ",
    ]
    long_text = "\n\n".join(premium_sections + ["Abschnitt " + str(i) + " lorem ipsum" for i in range(400)])

    async def fake_invoke(messages, settings):  # type: ignore[unused-argument]
        return json.dumps(
            {
                "short_summary": "Sehr lange Zusammenfassung.",
                "markdown_report": long_text,
                "followup_questions": [
                    "Welche Farbe ist gewuenscht?",
                    "Wie gross ist der Raum?",
                    "Welche Vorarbeiten wurden erledigt?",
                    "Gibt es Budgetvorgaben?",
                ],
            }
        )

    monkeypatch.setattr("agents.writer._invoke_writer_model", fake_invoke)

    report = await write_report(query, search_results, DEFAULT_WRITER)

    assert len(report.markdown_report) > 8000
    assert "| Position | Spezifikation" in report.markdown_report
    assert "## Premium-Laminat" in report.markdown_report
    assert 4 <= len(report.followup_questions) <= 6


@pytest.mark.asyncio
async def test_writer_rejects_non_diy(monkeypatch: pytest.MonkeyPatch) -> None:
    query = "Aktien kaufen"
    search_results = ["Einsteiger sollten sich ueber Brokergebuehren informieren."]

    async def fake_invoke(messages, settings):  # type: ignore[unused-argument]
        return json.dumps(
            {
                "short_summary": "Finanzanalyse",
                "markdown_report": "# Aktien",
                "followup_questions": ["Frage"],
            }
        )

    monkeypatch.setattr("agents.writer._invoke_writer_model", fake_invoke)

    report = await write_report(query, search_results, DEFAULT_WRITER)
    assert report.markdown_report == "# Aktien"

