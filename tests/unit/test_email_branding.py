"""Verifiziert das gebrandete HTML-Template des Emailers."""

from __future__ import annotations

from agents.emailer import _render_html
from agents.schemas import ReportData
from models.types import ProductItem


def _sample_report() -> ReportData:
    return ReportData(
        short_summary="Zusammenfassung",
        markdown_report=(
            "# Projekt X\n"
            "> **Meta:** Niveau Anfänger · Zeit 10–12 h · Budget 300–400 €\n\n"
            "## Vorbereitung\n- Liste\n\n"
            "## Einkaufsliste Bauhaus\n| Position | Beschreibung | Menge | Preis | Link |\n"
            "| --- | --- | --- | --- | --- |\n"
            "| 1 | Schrauben | 50 | ca. 9,95 € | https://www.bauhaus.info/p |\n\n"
            "## Schritt-für-Schritt\n1. Test\n**Prüfkriterium:** Prüfen\n"
        ),
        followup_questions=["Frage 1", "Frage 2", "Frage 3", "Frage 4"],
    )


def _sample_products() -> list[ProductItem]:
    return [
        ProductItem(
            title="Bauhaus MDF Platte",
            url="https://www.bauhaus.info/p/abc",
            note="18 mm, zugeschnitten",
            price_text="ca. 45 €",
        ),
        ProductItem(
            title="Bauhaus Schrauben",
            url="https://www.bauhaus.info/p/def",
            note="4x40 mm",
            price_text="ca. 9,95 €",
        ),
        ProductItem(
            title="Bauhaus Lack",
            url="https://www.bauhaus.de/p/ghi",
            note="Seidenmatt",
            price_text="ca. 22 €",
        ),
    ]


def test_email_branding_contains_header_toC_and_styling() -> None:
    html = _render_html(_sample_report(), product_results=_sample_products())

    assert "class=\"brand-header\"" in html
    assert "max-width: 720px" in html
    assert "prefers-color-scheme: dark" in html
    assert "class=\"button-primary\"" in html
    assert html.count("https://www.bauhaus") >= 3
    assert "mail.google.com" not in html

