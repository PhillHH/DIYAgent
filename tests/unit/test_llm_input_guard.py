"""Tests fuer den LLM-basierten Input-Guard."""

from __future__ import annotations

import json
from typing import Any

import pytest

from agents.model_settings import DEFAULT_PLANNER
from guards import llm_input_guard as guard_module


@pytest.fixture(autouse=True)
def enable_guards(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(guard_module, "LLM_GUARDS_ENABLED", True)


class _FakeMessage:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.parsed = payload
        self.content = json.dumps(payload)


class _FakeChoice:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.message = _FakeMessage(payload)


class _FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.choices = [_FakeChoice(payload)]


class _FakeChat:
    def __init__(self, payloads: list[dict[str, Any]]) -> None:
        self._payloads = payloads

    async def create(self, *args: Any, **kwargs: Any) -> _FakeResponse:  # type: ignore[override]
        return _FakeResponse(self._payloads.pop(0))


class _FakeClient:
    def __init__(self, payloads: list[dict[str, Any]]) -> None:
        self.chat = type("Chat", (), {"completions": _FakeChat(payloads)})()


@pytest.mark.asyncio
async def test_classify_query_llm_diy(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {"category": "DIY", "reasons": ["Werkzeug erwähnt"]}
    monkeypatch.setattr(guard_module, "_get_client", lambda: _FakeClient([payload]))

    result = await guard_module.classify_query_llm("Laminat verlegen", DEFAULT_PLANNER)
    assert result.category == "DIY"
    assert result.reasons == ["Werkzeug erwähnt"]


@pytest.mark.asyncio
async def test_classify_query_llm_ki_control(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {"category": "KI_CONTROL", "reasons": ["Fragt nach Steuerung"]}
    monkeypatch.setattr(guard_module, "_get_client", lambda: _FakeClient([payload]))

    result = await guard_module.classify_query_llm("Wie KI-Agenten steuern?", DEFAULT_PLANNER)
    assert result.category == "KI_CONTROL"


@pytest.mark.asyncio
async def test_classify_query_llm_reject(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {"category": "REJECT", "reasons": ["Nicht im Scope"]}
    monkeypatch.setattr(guard_module, "_get_client", lambda: _FakeClient([payload]))

    result = await guard_module.classify_query_llm("Aktien heute kaufen?", DEFAULT_PLANNER)
    assert result.category == "REJECT"


@pytest.mark.asyncio
async def test_classify_query_llm_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _raise(*args: Any, **kwargs: Any) -> None:  # type: ignore[unused-argument]
        raise RuntimeError("kaputt")

    class _FailClient:
        def __init__(self) -> None:
            self.chat = type("Chat", (), {"completions": type("Comp", (), {"create": _raise})()})()

    monkeypatch.setattr(guard_module, "_get_client", lambda: _FailClient())

    with pytest.raises(RuntimeError, match="Input-Guard nicht verfügbar"):
        await guard_module.classify_query_llm("Test", DEFAULT_PLANNER)

