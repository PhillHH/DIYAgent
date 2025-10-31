"""LLM-basierter Output-Guard fuer Endberichte ohne heuristische Fallbacks."""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from openai import AsyncOpenAI
from pydantic import ValidationError

from agents.model_settings import ModelSettings
from config import (
    GUARD_MODEL,
    GUARD_TEMPERATURE,
    LLM_GUARDS_ENABLED,
    OPENAI_API_KEY,
)
from guards.schemas import OutputGuardResult
from util.openai_tracing import traced_completion

_LOGGER = logging.getLogger(__name__)
_CLIENT: Optional[AsyncOpenAI] = None


def _get_client() -> AsyncOpenAI:
    if not OPENAI_API_KEY:
        raise RuntimeError("Output-Guard nicht verfügbar")
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = AsyncOpenAI(api_key=OPENAI_API_KEY)
    return _CLIENT


def _build_settings(settings: ModelSettings | None) -> ModelSettings:
    if settings is None:
        return ModelSettings(model=GUARD_MODEL, temperature=GUARD_TEMPERATURE)
    return settings


async def audit_report_llm(
    query: str,
    report_md: str,
    settings: ModelSettings | None,
) -> OutputGuardResult:
    """Prueft den Report via LLM; Fehler fuehren zu RuntimeError."""

    if not LLM_GUARDS_ENABLED:
        raise RuntimeError("Output-Guard nicht verfügbar")

    guard_settings = _build_settings(settings)
    messages = [
        {
            "role": "system",
            "content": (
                "Pruefe den Markdown-Report auf Richtlinien. Erlaubt: DIY-Inhalte oder Meta-Bewertungen zu KI-Steuerung. "
                "Verboten: unsichere Anleitungen (Elektrik/Gas ohne Fachkraft und Warnhinweise), medizinische/finanzielle Beratung, personenbezogene Daten. "
                "Antworte nur als JSON mit 'allowed', 'category' (DIY, KI_CONTROL, UNKNOWN) und 'issues'."
            ),
        },
        {"role": "user", "content": json.dumps({"query": query, "report": report_md})},
    ]

    response_format: dict[str, Any] = {
        "type": "json_schema",
        "json_schema": {
            "name": "OutputGuard",
            "schema": {
                "type": "object",
                "properties": {
                    "allowed": {"type": "boolean"},
                    "category": {
                        "type": "string",
                        "enum": ["DIY", "KI_CONTROL", "UNKNOWN"],
                    },
                    "issues": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["allowed", "category", "issues"],
                "additionalProperties": False,
            },
        },
    }

    try:
        client = _get_client()
        response = await traced_completion(
            "output_guard",
            guard_settings.model,
            {"messages": messages},
            lambda: client.chat.completions.create(
                model=guard_settings.model,
                messages=messages,
                temperature=0.0,
                response_format=response_format,
            ),
        )
        message = response.choices[0].message
        data = getattr(message, "parsed", None)
        if data is None:
            content = message.content or ""
            if not content.strip():
                raise ValueError("Leere Guard-Antwort")
            data = json.loads(content)
        return OutputGuardResult.model_validate(data)
    except (ValidationError, Exception) as exc:
        raise RuntimeError("Output-Guard nicht verfügbar") from exc
