"""Tests fuer das End-to-End-Probeskript im Mock-Modus."""

from __future__ import annotations

import types

import pytest

from scripts import e2e_probe


@pytest.fixture(autouse=True)
def set_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("SENDGRID_API_KEY", "test-key")
    monkeypatch.setenv("FROM_EMAIL", "sender@example.com")


class FakeClient:
    def __init__(self, status_sequence: list[dict[str, object]]) -> None:
        self._status_sequence = status_sequence
        self._polls = 0

    def __enter__(self) -> "FakeClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        return None

    def post(self, url: str, json: dict) -> types.SimpleNamespace:  # type: ignore[override]
        return types.SimpleNamespace(status_code=200, json=lambda: {"job_id": "fake-job"}, raise_for_status=lambda: None)

    def get(self, url: str) -> types.SimpleNamespace:  # type: ignore[override]
        response = self._status_sequence[min(self._polls, len(self._status_sequence) - 1)]
        self._polls += 1
        return types.SimpleNamespace(status_code=200, json=lambda: response, raise_for_status=lambda: None)


def test_e2e_probe_success(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    fake_client = FakeClient(
        [
            {"phase": "queued", "detail": None, "payload": None, "job_id": "fake-job"},
            {
                "phase": "done",
                "detail": None,
                "payload": {
                    "email_links": ["https://www.bauhaus.info/test"],
                    "email_preview": "<html>",
                    "report_payload": {"title": "Projekt X"},
                },
                "job_id": "fake-job",
            },
        ]
    )
    monkeypatch.setattr("httpx.Client", lambda timeout=30: fake_client)  # type: ignore[assignment]
    monkeypatch.setattr(e2e_probe, "time", types.SimpleNamespace(monotonic=lambda: 0.0, sleep=lambda _x: None))

    exit_code = e2e_probe.main(["--email", "user@example.com", "--timeout", "10", "--interval", "1"])
    captured = capsys.readouterr().out

    assert exit_code == 0
    assert "Phase 'queued'" in captured
    assert "Finaler Status: done" in captured


def test_e2e_probe_error(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_client = FakeClient([
        {"phase": "error", "detail": "Simulierter Fehler", "payload": None, "job_id": "fake-job"}
    ])
    monkeypatch.setattr("httpx.Client", lambda timeout=30: fake_client)  # type: ignore[assignment]
    monkeypatch.setattr(e2e_probe, "time", types.SimpleNamespace(monotonic=lambda: 0.0, sleep=lambda _x: None))

    exit_code = e2e_probe.main(["--email", "user@example.com"])

    assert exit_code == 1

