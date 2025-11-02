"""Tests zur Struktur des Writer-Prompts."""

from __future__ import annotations

from agents import writer


def test_compose_messages_contains_new_sections_without_laminat() -> None:
    payload = "{}"
    messages = writer._compose_messages(payload, category=None, product_results=[])

    system_prompt = messages[0]["content"]
    assert "Einkaufsliste (Bauhaus-Links)" in system_prompt
    assert "Schritt-für-Schritt" in system_prompt
    assert "Premium-Laminat" not in system_prompt
    assert "(#" in system_prompt


def test_compose_messages_includes_product_hint() -> None:
    payload = "{}"
    sample_products = [{"title": "MDF"}]
    messages = writer._compose_messages(payload, category=None, product_results=sample_products)

    system_prompt = messages[0]["content"]
    assert "produktdaten" in system_prompt.lower()
    assert "bauhaus" in system_prompt.lower()

