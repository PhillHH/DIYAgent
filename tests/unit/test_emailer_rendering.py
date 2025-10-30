"""Tests fuer die Premium-E-Mail-Ausgabe."""

from __future__ import annotations

import types

import pytest

from agents.emailer import MAX_EMAIL_SIZE, _render_html, send_email
from agents.schemas import ReportData


def test_emailer_rendering_contains_toc_and_tables() -> None:
    markdown = """
# Premium Projekt

## Abschnitt A
Text.

## Abschnitt B
### Unterpunkt

| Position | Spezifikation | Menge | Stückpreis | Summe |
| --- | --- | --- | --- | --- |
| 1 | Holzbrett | 5 | 12 | 60 |
"""
    report = ReportData(short_summary="Kurz", markdown_report=markdown, followup_questions=[])
    html = _render_html(report)
    assert "nav class=\"toc\"" in html
    assert "class=\"table\"" in html


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

