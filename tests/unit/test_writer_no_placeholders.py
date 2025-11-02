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

    markdown = (
        "# Projekt\n\n"
        "## Inhaltsverzeichnis\n"
        "- [Vorbereitung](#vorbereitung)\n"
        "- [Einkaufsliste (Bauhaus-Links)](#einkaufsliste-bauhaus-links)\n\n"
        "## Vorbereitung\nText\n\n"
        "## Schritt-für-Schritt\n1. Schritt\n**Prüfkriterium:** Test\n\n"
        "## Qualität & Sicherheit\nText\n\n"
        "## Zeit & Kosten\n| Paket | Dauer | Kosten |\n| --- | --- | --- |\n"
        "## FAQ\n### Frage?\nAntwort."
    )

    async def fake_invoke(messages, settings):  # type: ignore[unused-argument]
        return json.dumps(
            {
                "short_summary": "Kurz",
                "markdown_report": markdown,
                "followup_questions": [
                    "Frage 1",
                    "Frage 2",
                    "Frage 3",
                    "Frage 4",
                ],
            }
        )

    monkeypatch.setattr("agents.writer._invoke_writer_model", fake_invoke)

    report = await write_report(query, search_results, DEFAULT_WRITER, product_results=[])

    assert "Keine geprüften Bauhaus-Produkte verfügbar" in report.markdown_report

    einkauf_index = report.markdown_report.lower().find("## einkaufsliste (bauhaus-links)")
    assert einkauf_index != -1
    einkauf_section = report.markdown_report[einkauf_index:]
    assert "http" not in einkauf_section

