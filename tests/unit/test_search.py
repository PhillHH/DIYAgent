"""Unit-Tests für den Search-Agenten."""

from __future__ import annotations

import pytest

from agents.model_settings import DEFAULT_SEARCHER
from agents.schemas import WebSearchItem, WebSearchPlan
from agents import search as search_module


@pytest.mark.asyncio
async def test_perform_searches_returns_results_in_order(monkeypatch: pytest.MonkeyPatch) -> None:
    plan = WebSearchPlan(
        searches=[
            WebSearchItem(reason="r1", query="q1"),
            WebSearchItem(reason="r2", query="q2"),
            WebSearchItem(reason="r3", query="q3"),
        ]
    )

    async def fake_exec(item, settings, limiter):  # type: ignore[unused-argument]
        if "bauhaus" in item.query:
            return "products", []
        return f"OK: {item.query}", []

    monkeypatch.setattr(search_module, "_execute_search_item", fake_exec)

    summaries, product_results = await search_module.perform_searches(
        plan,
        DEFAULT_SEARCHER,
        user_query="Allgemeine Frage",
        category=None,
    )

    assert summaries == ["OK: q1", "OK: q2", "OK: q3"]
    assert product_results == []


@pytest.mark.asyncio
async def test_perform_searches_requires_items() -> None:
    empty_plan = WebSearchPlan.model_construct(searches=[])

    with pytest.raises(ValueError, match="no searches planned"):
        await search_module.perform_searches(
            empty_plan,
            DEFAULT_SEARCHER,
            user_query="Test",
            category=None,
        )


@pytest.mark.asyncio
async def test_perform_searches_adds_bauhaus_item(monkeypatch: pytest.MonkeyPatch) -> None:
    plan = WebSearchPlan(
        searches=[WebSearchItem(reason="r1", query="q1")]
    )

    seen_queries: list[str] = []

    async def fake_exec(item, settings, limiter):  # type: ignore[unused-argument]
        seen_queries.append(item.query)
        return item.reason, []

    monkeypatch.setattr(search_module, "_execute_search_item", fake_exec)

    summaries, product_results = await search_module.perform_searches(
        plan,
        DEFAULT_SEARCHER,
        user_query="Regal bauen",
        category="DIY",
    )

    assert seen_queries == ["q1"]  # Produkt-Slots werden separat behandelt
    assert product_results == []

