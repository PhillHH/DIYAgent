"""Unit-Tests für den DIY-WebSearch Planner."""

from __future__ import annotations

import json

import pytest

from agents.model_settings import DEFAULT_PLANNER
from agents.schemas import WebSearchPlan
from agents.planner import plan_searches
from config.settings import HOW_MANY_SEARCHES


@pytest.mark.asyncio
async def test_planner_valid_query(monkeypatch: pytest.MonkeyPatch) -> None:
    query = "Laminat im Wohnzimmer verlegen"

    searches = [
        {"reason": f"Grund {idx}", "query": f"Query {idx}"}
        for idx in range(HOW_MANY_SEARCHES)
    ]

    async def fake_invoke(_query, _settings, _attempt):  # type: ignore[unused-argument]
        return json.dumps({"searches": searches})

    monkeypatch.setattr("agents.planner._invoke_planner_model", fake_invoke)

    plan = await plan_searches(query=query, settings=DEFAULT_PLANNER)

    assert len(plan.searches) == HOW_MANY_SEARCHES + 1
    for item in plan.searches:
        assert item.reason
        assert item.query


@pytest.mark.asyncio
async def test_planner_non_diy_query_raises() -> None:
    query = "Aktienkurs Apple"

    with pytest.raises(ValueError):
        await plan_searches(query=query, settings=DEFAULT_PLANNER)


@pytest.mark.asyncio
async def test_planner_rejects_when_model_returns_reject(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_invoke(_query, _settings, _attempt):  # type: ignore[unused-argument]
        return "REJECT"

    monkeypatch.setattr("agents.planner._invoke_planner_model", fake_invoke)

    with pytest.raises(ValueError):
        await plan_searches("Regal bauen", DEFAULT_PLANNER)

