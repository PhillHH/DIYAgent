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

    report_markdown = "\n".join(
        [
            "# Premium Projekt",
            "> **Meta:** Niveau Anfänger · Zeit 14–18 h · Budget 250–450 €",
            "",
            "## Inhaltsverzeichnis",
            "- [Vorbereitung](#vorbereitung)",
            "- [Einkaufsliste Bauhaus](#einkaufsliste-bauhaus)",
            "- [Schritt-für-Schritt](#schritt-fuer-schritt)",
            "- [Qualität & Sicherheit](#qualitaet-sicherheit)",
            "- [Zeit & Kosten](#zeit-kosten)",
            "- [FAQ](#faq)",
            "",
            "## Vorbereitung",
            "- Raum vorbereiten",
            "",
            "## Einkaufsliste Bauhaus",
            "| Position | Beschreibung | Menge | Preis | Link |",
            "| --- | --- | --- | --- | --- |",
            "| 1 | MDF Platte | 3 | ca. 45 € | https://www.bauhaus.info/p |",
            "",
            "## Schritt-für-Schritt",
            "1. Schritt eins\n**Prüfkriterium:** Oberfläche glatt",
            "2. Schritt zwei\n**Prüfkriterium:** Farbe deckend",
            "",
            "## Qualität & Sicherheit",
            "- PSA tragen",
            "",
            "## Zeit & Kosten",
            "| Paket | Dauer | Kosten |",
            "| --- | --- | --- |",
            "| Vorbereitung | 4 h | ca. 60 € |",
            "",
            "## FAQ",
            "### Wie lange trocknet die Farbe?",
            "Ungefaehr 12 Stunden.",
        ]
        + ["Abschnitt " + str(i) + " lorem ipsum" for i in range(200)]
    )

    async def fake_invoke(messages, settings):  # type: ignore[unused-argument]
        return json.dumps(
            {
                "short_summary": "Sehr lange Zusammenfassung.",
                "markdown_report": report_markdown,
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

    assert "## Premium-Laminat" not in report.markdown_report
    assert "## Einkaufsliste (Bauhaus-Links)" in report.markdown_report
    assert "**Prüfkriterium:**" in report.markdown_report
    assert "(#" in report.markdown_report
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
    assert report.markdown_report.startswith("# Aktien")
    assert "Keine geprüften Bauhaus-Produkte verfügbar" in report.markdown_report

