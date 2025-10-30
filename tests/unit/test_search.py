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

    async def fake_invoke(item, settings, limiter):  # type: ignore[unused-argument]
        return f"OK: {item.query}"

    monkeypatch.setattr(search_module, "_invoke_search_model", fake_invoke)

    results = await search_module.perform_searches(plan, DEFAULT_SEARCHER)

    assert results == ["OK: q1", "OK: q2", "OK: q3"]


@pytest.mark.asyncio
async def test_perform_searches_requires_items() -> None:
    empty_plan = WebSearchPlan.model_construct(searches=[])

    with pytest.raises(ValueError, match="no searches planned"):
        await search_module.perform_searches(empty_plan, DEFAULT_SEARCHER)

