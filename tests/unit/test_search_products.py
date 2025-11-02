"""Tests fuer die Bauhaus-Produktsuche."""

from __future__ import annotations

import json

from agents import search
from agents.schemas import WebSearchItem


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


def test_is_product_search_detects_bauhaus_queries() -> None:
    item = WebSearchItem(reason="Einkaufsliste Bauhaus", query="Materialien site:bauhaus.info")
    assert search._is_product_search(item) is True

    normal_item = WebSearchItem(reason="Allgemein", query="Tipps zum Streichen")
    assert search._is_product_search(normal_item) is False

