"""Tests fuer die Bauhaus-Produktsuche."""

from __future__ import annotations

import pytest

import json

from agents import search
from agents.model_settings import DEFAULT_SEARCHER
from models.types import ProductItem


def test_parse_product_response_filters_non_bauhaus_links() -> None:
    payload = {
        "items": [
            {
                "title": "Bauhaus MDF",
                "url": "https://www.bauhaus.info/mdf?utm_source=test",
                "note": "18 mm",
                "price_text": "ca. 45 €",
            },
            {
                "title": "Bauhaus Schrauben",
                "url": "bauhaus.de/schrauben?fbclid=abc123",
                "price_text": "ca. 5,99 €",
            },
            {
                "title": "Bauhaus Lack",
                "url": "https://www.bauhaus.at/lack#section",
                "note": "Seidenmatt",
            },
            {
                "title": "Fremdlink",
                "url": "https://example.com/product",
            },
        ]
    }

    products = search._parse_product_response(json.dumps(payload))

    assert len(products) == 3
    assert all(str(product.url).startswith("https://www.bauhaus") for product in products)
    assert all("?" not in str(product.url) and "#" not in str(product.url) for product in products)


def test_parse_product_response_markdown_fallback() -> None:
    markdown = (
        "- [Schraubenset verzinkt](https://www.bauhaus.de/schrauben/verzinkt) – Set mit 120 Stk.\n"
        "- [Multiplexplatte 18 mm](https://www.bauhaus.at/multiplex/platte18mm)\n"
    )

    products = search._parse_product_response(markdown)

    assert len(products) == 2
    assert str(products[0].url) == "https://www.bauhaus.de/schrauben/verzinkt"
    assert products[0].note == "Set mit 120 Stk."


@pytest.mark.asyncio
async def test_perform_product_enrichment_uses_context(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    async def fake_invoke(query, settings, limiter, *, context=None):  # type: ignore[unused-argument]
        captured["query"] = query
        captured["context"] = context
        return "ok", [
            ProductItem(
                title="Bauhaus Test",
                url="https://www.bauhaus.de/test",
                note=None,
                price_text=None,
            )
        ]

    monkeypatch.setattr(search, "_invoke_product_search", fake_invoke)

    products = await search.perform_product_enrichment(
        "Waschbecken austauschen",
        ["Zusammenfassung A", "Zusammenfassung B"],
        DEFAULT_SEARCHER,
    )

    assert len(products) == 1
    assert "Waschbecken austauschen" in captured["query"]
    assert isinstance(captured["context"], str)
    assert "Zusammenfassung" in captured["context"]

