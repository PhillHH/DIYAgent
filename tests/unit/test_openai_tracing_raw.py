"""Tests fuer das OpenAI-Tracing-Modul."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import config
from util.openai_tracing import traced_completion


class FakeResponse:
    """Minimaler Ersatz fuer eine OpenAI-Antwort."""

    def __init__(self, content: str) -> None:
        self.output_text = content

    def model_dump(self) -> dict:
        return {"output_text": self.output_text}


@pytest.mark.asyncio
async def test_traced_completion_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "LOG_DIR", str(tmp_path))
    monkeypatch.setattr(config, "OPENAI_TRACING_ENABLED", True)
    monkeypatch.setattr(config, "OPENAI_TRACE_RAW", True)

    async def fake_call():
        return FakeResponse("OK")

    result = await traced_completion("planner", "gpt-4o-mini", {"msg": "hi"}, fake_call)
    assert isinstance(result, FakeResponse)

    log_file = tmp_path / "openai.log"
    entry = json.loads(log_file.read_text(encoding="utf-8").strip())
    assert entry["call_name"] == "planner"
    assert entry["prompt_raw"].startswith("{")
    assert entry["output_raw"] == '{"output_text": "OK"}'
    assert entry["error"] is None
    assert entry["duration_ms"] >= 0


@pytest.mark.asyncio
async def test_traced_completion_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "LOG_DIR", str(tmp_path))
    monkeypatch.setattr(config, "OPENAI_TRACING_ENABLED", True)
    monkeypatch.setattr(config, "OPENAI_TRACE_RAW", True)

    async def fake_call():
        raise RuntimeError("kaputt")

    with pytest.raises(RuntimeError):
        await traced_completion("planner", "gpt-4o-mini", "prompt", fake_call)

    log_file = tmp_path / "openai.log"
    entry = json.loads(log_file.read_text(encoding="utf-8").strip())
    assert entry["error"].startswith("RuntimeError")
    assert entry["prompt_raw"] == "prompt"

