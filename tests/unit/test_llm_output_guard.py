"""Tests fuer den LLM-basierten Output-Guard."""

from __future__ import annotations

import json
from typing import Any

import pytest

from agents.model_settings import DEFAULT_WRITER
from guards import llm_output_guard as guard_module


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
async def test_audit_report_llm_allows_content(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {"allowed": True, "issues": [], "category": "DIY"}
    monkeypatch.setattr(guard_module, "_get_client", lambda: _FakeClient([payload]))

    result = await guard_module.audit_report_llm("Laminat verlegen", "# Report", DEFAULT_WRITER)
    assert result.allowed is True
    assert result.category == "DIY"


@pytest.mark.asyncio
async def test_audit_report_llm_blocks_content(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {"allowed": False, "issues": ["Unsichere Anleitung"], "category": "UNKNOWN"}
    monkeypatch.setattr(guard_module, "_get_client", lambda: _FakeClient([payload]))

    result = await guard_module.audit_report_llm("Laminat", "# Gefährliche Anleitung", DEFAULT_WRITER)
    assert result.allowed is False
    assert "Unsichere Anleitung" in result.issues


@pytest.mark.asyncio
async def test_audit_report_llm_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FailClient:
        def __init__(self) -> None:
            async def _raise(*args: Any, **kwargs: Any) -> None:  # type: ignore[unused-argument]
                raise RuntimeError("kaputt")

            self.chat = type("Chat", (), {"completions": type("Comp", (), {"create": _raise})()})()

    monkeypatch.setattr(guard_module, "_get_client", lambda: _FailClient())

    with pytest.raises(RuntimeError, match="Output-Guard nicht verfügbar"):
        await guard_module.audit_report_llm("Laminat", "# Laminat", DEFAULT_WRITER)

