"""OpenAI-Tracing-Helfer fuer detailliertes Logging von Modellaufrufen."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable

import config

# Einfache Kostenschaetzung pro 1K Tokens (USD) – konservative Werte fuer Prototyping.
_MODEL_PRICES = {
    "gpt-4o-mini": {"input": 0.00015, "output": 0.00060},
}

if config.OPENAI_TRACING_ENABLED:
    os.environ.setdefault("OPENAI_ENABLE_TRACING", "true")


def _ensure_log_dir() -> Path:
    """Stellt sicher, dass der Log-Ordner existiert."""

    log_dir = Path(config.LOG_DIR or "logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def _serialize_prompt(prompt: Any) -> str:
    """Serialisiert den Prompt in einen JSON- oder Text-String."""

    if isinstance(prompt, (dict, list)):
        return json.dumps(prompt, ensure_ascii=False)
    return str(prompt)


def _serialize_output(result: Any) -> str:
    """Serialisiert das Ergebnis moeglichst verlustfrei."""

    if hasattr(result, "model_dump"):
        return json.dumps(result.model_dump(), ensure_ascii=False)
    if isinstance(result, dict):
        return json.dumps(result, ensure_ascii=False)
    return str(result)


def _estimate_tokens(char_count: int) -> int:
    """Grobe Schaetzung: 1 Token ≈ 4 Zeichen."""

    if char_count <= 0:
        return 0
    return max(1, char_count // 4)


def _estimate_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    """Berechnet die erwarteten Kosten in USD basierend auf der Preistabelle."""

    prices = _MODEL_PRICES.get(model, {"input": 0.0, "output": 0.0})
    cost = (tokens_in / 1000) * prices["input"] + (tokens_out / 1000) * prices["output"]
    return round(cost, 6)


async def traced_completion(
    call_name: str,
    model: str,
    prompt: Any,
    invoke: Callable[[], Awaitable[Any]],
) -> Any:
    """Führt einen OpenAI-Aufruf aus und schreibt einen Trace-Eintrag.

    Args:
        call_name: Logischer Name des Aufrufs (z. B. "planner").
        model: Name des OpenAI-Modells.
        prompt: Rohprompt (dict/list/str).
        invoke: Coroutine-Factory, die den eigentlichen Modellaufruf ausführt.

    Returns:
        Ergebnis des Modellaufrufs (Originalobjekt).
    """

    if not config.OPENAI_TRACING_ENABLED:
        return await invoke()

    trace_raw = config.OPENAI_TRACE_RAW
    prompt_serialized = _serialize_prompt(prompt)
    prompt_chars = len(prompt_serialized)

    start = time.perf_counter()
    error_info = None
    output_serialized = ""
    result: Any = None

    try:
        result = await invoke()
        output_serialized = _serialize_output(result)
    except Exception as exc:  # pragma: no cover - Fehlerfall wird separat getestet
        error_info = f"{type(exc).__name__}: {exc}"
        _write_trace(
            call_name,
            model,
            start,
            prompt_serialized,
            prompt_chars,
            output_serialized,
            error_info,
        )
        raise

    _write_trace(
        call_name,
        model,
        start,
        prompt_serialized,
        prompt_chars,
        output_serialized,
        error_info,
    )
    return result


def _write_trace(
    call_name: str,
    model: str,
    start: float,
    prompt_serialized: str,
    prompt_chars: int,
    output_serialized: str,
    error_info: str | None,
) -> None:
    """Schreibt einen JSON-Trace-Eintrag in die Logdatei."""

    duration_ms = round((time.perf_counter() - start) * 1000, 3)
    output_chars = len(output_serialized)
    tokens_in = _estimate_tokens(prompt_chars)
    tokens_out = _estimate_tokens(output_chars)
    cost_est = _estimate_cost(model, tokens_in, tokens_out)

    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "call_name": call_name,
        "model": model,
        "duration_ms": duration_ms,
        "prompt_raw": prompt_serialized if config.OPENAI_TRACE_RAW else "[maskiert]",
        "prompt_chars": prompt_chars,
        "output_raw": output_serialized if config.OPENAI_TRACE_RAW else "[maskiert]",
        "output_chars": output_chars,
        "tokens_in_est": tokens_in,
        "tokens_out_est": tokens_out,
        "cost_est_usd": cost_est,
        "error": error_info,
    }

    if call_name in {"search_products", "writer_email"}:
        entry["highlight"] = True

    log_file = _ensure_log_dir() / "openai.log"
    with log_file.open("a", encoding="utf-8") as file:
        file.write(json.dumps(entry, ensure_ascii=False) + "\n")
