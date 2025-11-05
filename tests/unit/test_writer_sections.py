"""Tests zur Struktur des Writer-Prompts."""

from __future__ import annotations

from agents import writer


def test_compose_messages_contains_new_sections_without_laminat() -> None:
    payload = "{}"
    messages = writer._compose_messages_diy(payload, "Testprojekt", [])

    system_prompt = messages[0]["content"]
    assert "ShoppingItem" in system_prompt
    assert "mindestens sechs" in system_prompt
    assert "Schritt-für-Schritt" in system_prompt
    assert "FAQ genau 5 Einträge" in system_prompt
    assert "Followups 4–6" in system_prompt


def test_compose_messages_includes_product_hint() -> None:
    payload = "{}"
    sample_products = [{"title": "MDF"}]
    messages = writer._compose_messages_diy(payload, "Testprojekt", sample_products)

    system_prompt = messages[0]["content"]
    assert "product_results" in system_prompt
    assert "bauhaus" in system_prompt.lower()

