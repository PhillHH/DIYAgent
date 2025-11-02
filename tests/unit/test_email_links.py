"""Tests fuer die Einkaufsliste im E-Mail-Renderer."""

from __future__ import annotations

from agents.emailer import _render_html
from agents.schemas import ReportData
from models.types import ProductItem


def test_email_einkaufsliste_contains_only_bauhaus_links() -> None:
    report = ReportData(
        short_summary="Kurz",
        markdown_report="# Projekt\n\n## Vorbereitung\nInhalt",
        followup_questions=["A", "B", "C", "D"],
    )

    products = [
        ProductItem(title="Artikel 1", url="https://www.bauhaus.info/a?utm=123", note=None, price_text="ca. 10 €"),
        ProductItem(title="Artikel 2", url="https://www.bauhaus.de/b#frag", note=None, price_text="ca. 20 €"),
        ProductItem(title="Artikel 3", url="https://www.bauhaus.at/c", note="Hinweis", price_text="ca. 30 €"),
    ]

    html = _render_html(report, product_results=products)

    assert html.count("https://www.bauhaus") >= 3
    assert "utm=" not in html
    assert "mail.google.com" not in html

