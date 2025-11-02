"""Tests fuer den E-Mail-Agenten."""

from __future__ import annotations

import types

import pytest

from agents.emailer import send_email
from agents.schemas import ReportData
from models.types import ProductItem


class DummyResponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


@pytest.mark.asyncio
async def test_send_email_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    report = ReportData(
        short_summary="Kurzinfo zum Streichen",
        markdown_report="# Projekt\n\n## Kurzfassung\nAlles DIY.\n\n- Schritt 1",
        followup_questions=["Frage 1", "Frage 2", "Frage 3"],
    )

    async def fake_post(payload):  # type: ignore[unused-argument]
        return DummyResponse(202)

    monkeypatch.setattr("agents.emailer._post_sendgrid", fake_post)

    products = [
        ProductItem(
            title="Bauhaus Test",
            url="https://www.bauhaus.info/p/test",
            note="",
            price_text="ca. 10 €",
        )
    ]

    result = await send_email(report, "user@example.com", product_results=products)

    assert result["status"] == "sent"
    assert result["status_code"] == 202
    assert any("bauhaus" in link for link in result.get("links", []))


@pytest.mark.asyncio
async def test_send_email_invalid_report(monkeypatch: pytest.MonkeyPatch) -> None:
    report = ReportData(short_summary="", markdown_report="", followup_questions=[])

    with pytest.raises(ValueError):
        await send_email(report, "invalid-email")

