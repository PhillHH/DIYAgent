"""Tests fuer die Payload-Erstellung des Search-Agenten."""

from __future__ import annotations

import types

import pytest

import config
from agents.model_settings import DEFAULT_SEARCHER
from agents.schemas import WebSearchItem, WebSearchPlan
from agents import search as search_module


def test_validate_payload_rejects_forbidden_key() -> None:
    with pytest.raises(ValueError):
        search_module._validate_payload({"tool_choice": {"name": "verboten"}})


@pytest.mark.asyncio
async def test_search_payload_without_forbidden_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    plan = WebSearchPlan(searches=[WebSearchItem(reason="Test", query="Laminate verlegen")])

    monkeypatch.setattr(config, "OPENAI_WEB_TOOL_TYPE", "web_search_preview")

    recorded = {}

    async def fake_create(**kwargs):
        recorded["payload"] = kwargs
        return types.SimpleNamespace(output_text="Zusammenfassung")

    fake_client = types.SimpleNamespace(
        responses=types.SimpleNamespace(create=fake_create)
    )

    monkeypatch.setattr(search_module, "_get_client", lambda: fake_client)

    result = await search_module.perform_searches(plan, DEFAULT_SEARCHER)

    assert result[0] == "Zusammenfassung"
    payload = recorded["payload"]
    assert "tool_choice.name" not in payload
    assert "tool_choice.tool" not in payload
    assert payload.get("tool_choice") == "auto"
    assert payload["tools"] == [{"type": "web_search_preview"}]


@pytest.mark.asyncio
async def test_search_fallback_without_tool_choice(monkeypatch: pytest.MonkeyPatch) -> None:
    plan = WebSearchPlan(searches=[WebSearchItem(reason="Test", query="Laminate verlegen")])

    monkeypatch.setattr(config, "OPENAI_WEB_TOOL_TYPE", "web_search_preview")

    attempts = []

    async def fake_create(**kwargs):
        attempts.append(kwargs)
        if len(attempts) == 1:
            raise RuntimeError("unknown parameter: tool_choice")
        return types.SimpleNamespace(output_text="Fallback")

    fake_client = types.SimpleNamespace(
        responses=types.SimpleNamespace(create=fake_create)
    )

    monkeypatch.setattr(search_module, "_get_client", lambda: fake_client)

    result = await search_module.perform_searches(plan, DEFAULT_SEARCHER)

    assert result[0] == "Fallback"
    assert attempts[0]["tool_choice"] == "auto"
    assert "tool_choice" not in attempts[1]

