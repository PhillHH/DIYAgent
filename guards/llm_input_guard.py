"""LLM-basierter Input-Guard zur Klassifikation von Anfragen ohne Heuristiken."""

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
from guards.schemas import InputGuardResult
from util.openai_tracing import traced_completion

_LOGGER = logging.getLogger(__name__)
_CLIENT: Optional[AsyncOpenAI] = None


def _get_client() -> AsyncOpenAI:
    if not OPENAI_API_KEY:
        raise RuntimeError("Input-Guard nicht verfügbar")
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = AsyncOpenAI(api_key=OPENAI_API_KEY)
    return _CLIENT


def _build_settings(settings: ModelSettings | None) -> ModelSettings:
    if settings is None:
        return ModelSettings(model=GUARD_MODEL, temperature=GUARD_TEMPERATURE)
    return settings


async def classify_query_llm(query: str, settings: ModelSettings | None) -> InputGuardResult:
    """Klassifiziert eine Anfrage ueber das LLM; Fehler fuehren zu RuntimeError."""

    if not LLM_GUARDS_ENABLED:
        raise RuntimeError("Input-Guard nicht verfügbar")

    guard_settings = _build_settings(settings)
    messages = [
        {
            "role": "system",
            "content": (
                "Klassifiziere die Nutzeranfrage eindeutig: DIY, KI_CONTROL (Meta-Themen wie KI-Steuerung/Evaluierung, Guardrails, Orchestrierung), "
                "REJECT (alles andere). DIY umfasst klassische Heimwerker-Arbeiten in Haus, Wohnung oder Garten (z. B. Laminat verlegen, Waschbecken tauschen, Regale montieren, Streichen, Reparaturen). "
                "Nur REJECT, wenn es um fachfremde Themen wie Medizin, Finanzen, kontroverse Politik, illegale Inhalte oder riskante Arbeiten geht, die ohne Fachkraft nicht erlaubt sind. "
                "Antworte nur als JSON mit den Feldern 'category' und 'reasons' (Liste von Begruendungen)."
            ),
        },
        {"role": "user", "content": query},
    ]

    response_format: dict[str, Any] = {
        "type": "json_schema",
        "json_schema": {
            "name": "InputGuard",
            "schema": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "enum": ["DIY", "KI_CONTROL", "REJECT"]},
                    "reasons": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1,
                        "maxItems": 3,
                    },
                },
                "required": ["category", "reasons"],
                "additionalProperties": False,
            },
        },
    }

    try:
        client = _get_client()
        response = await traced_completion(
            "input_guard",
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
        return InputGuardResult.model_validate(data)
    except (ValidationError, Exception) as exc:
        raise RuntimeError("Input-Guard nicht verfügbar") from exc
