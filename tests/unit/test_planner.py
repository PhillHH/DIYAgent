"""Unit-Tests für den DIY-WebSearch Planner."""

from __future__ import annotations

import json

import pytest

from agents.model_settings import DEFAULT_PLANNER
from agents.schemas import WebSearchPlan
from agents.planner import plan_searches
from agents.schemas import SearchPhase
from config.settings import HOW_MANY_SEARCHES


@pytest.mark.asyncio
async def test_planner_valid_query(monkeypatch: pytest.MonkeyPatch) -> None:
    query = "Laminat im Wohnzimmer verlegen"

    searches = [
        {
            "reason": SearchPhase.VORBEREITUNG_PLANUNG.value,
            "query": "Vorbereitung: Untergrundprüfung, Maße, Werkzeugplanung, Reihenfolge, Raumlogistik, Schutzmaßnahmen",
        },
        {
            "reason": SearchPhase.MATERIAL_WERKZEUGE.value,
            "query": "Materialliste Laminat Wohnzimmer: Paneele, Dämmung, Übergangsprofile, Sockelleisten, Verlegewerkzeuge, Mengenberechnung",
        },
        {
            "reason": SearchPhase.SICHERHEIT_UMWELT.value,
            "query": "Sicherheitscheck Laminat: PSA, Staubschutz, Emissionen, Stromzonen, Entsorgung Altbelag, Stolperfallen",
        },
    ]

    async def fake_invoke(_query, _settings, _attempt):  # type: ignore[unused-argument]
        return json.dumps({"searches": searches})

    monkeypatch.setattr("agents.planner._invoke_planner_model", fake_invoke)

    plan = await plan_searches(query=query, settings=DEFAULT_PLANNER)

    assert 1 <= len(plan.searches) <= 10
    reasons = {item.reason for item in plan.searches}
    assert SearchPhase.VORBEREITUNG_PLANUNG in reasons
    assert SearchPhase.MATERIAL_WERKZEUGE in reasons
    assert SearchPhase.SICHERHEIT_UMWELT in reasons
    assert SearchPhase.OPTIONEN_UPGRADES in reasons


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

