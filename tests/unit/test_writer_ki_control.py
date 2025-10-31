"""Tests fuer den Writer im KI_CONTROL-Modus."""

from __future__ import annotations

import json

import pytest

from agents.model_settings import DEFAULT_WRITER
from agents.writer import write_report


@pytest.mark.asyncio
async def test_writer_ki_control_template(monkeypatch: pytest.MonkeyPatch) -> None:
    query = "Wie KI-Agenten im Heimwerker-Kontext steuern?"
    search_results = ["Zusammenfassung 1", "Zusammenfassung 2"]

    markdown = "\n".join(
        [
            "# KI Governance Report",
            "## Ziel & Kontext",
            "## Steuerbare Aspekte",
            "## Risiken & Mitigations",
            "## Metriken",
            "## Evaluationsplan",
            "## Governance",
            "## Empfehlungen & Roadmap",
            "## FAQ",
        ]
    )

    async def fake_invoke(messages, settings):  # type: ignore[unused-argument]
        return json.dumps(
            {
                "short_summary": "Kurz",
                "markdown_report": markdown,
                "followup_questions": [
                    "Wie sieht der Zeitplan aus?",
                    "Welche Tools werden eingesetzt?",
                    "Wer ueberwacht die Umsetzung?",
                    "Welche KPIs gelten als erfolgreich?",
                ],
            }
        )

    monkeypatch.setattr("agents.writer._invoke_writer_model", fake_invoke)

    report = await write_report(query, search_results, DEFAULT_WRITER, category="KI_CONTROL")

    assert "## Steuerbare Aspekte" in report.markdown_report
    assert "## Empfehlungen & Roadmap" in report.markdown_report
    assert report.followup_questions

