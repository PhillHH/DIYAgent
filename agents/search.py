"""Async-Implementierung fuer Web-Suchoperationen mit OpenAI."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import List, Optional

from aiolimiter import AsyncLimiter
from openai import AsyncOpenAI
from tenacity import AsyncRetrying, RetryError, stop_after_attempt, wait_exponential_jitter
from uuid import uuid4

from agents.model_settings import ModelSettings
from agents.schemas import WebSearchItem, WebSearchPlan
from config import (
    DEFAULT_TIMEOUT,
    MAX_CONCURRENCY,
    OPENAI_API_KEY,
    OPENAI_TRACING_ENABLED,
    OPENAI_WEB_TOOL_TYPE,
)
from util.openai_tracing import traced_completion
from util import extract_output_text

_CLIENT: Optional[AsyncOpenAI] = None
_LOGGER = logging.getLogger(__name__)
_FORBIDDEN_KEYS = {"tool_choice.name", "tool_choice.tool"}


def _get_client() -> AsyncOpenAI:
    """Liefert einen wiederverwendbaren OpenAI-Client.

    Raises:
        ValueError: Wenn kein `OPENAI_API_KEY` vorhanden ist.

    Returns:
        Instanz des asynchronen OpenAI-Clients.
    """

    global _CLIENT
    if _CLIENT is None:
        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY ist nicht gesetzt")
        _CLIENT = AsyncOpenAI(api_key=OPENAI_API_KEY)
    return _CLIENT


async def perform_searches(plan: WebSearchPlan, settings: ModelSettings) -> List[str]:
    """Generiert fuer jede geplante Suche eine Kurz-Zusammenfassung.

    Args:
        plan: Vom Planner erzeugter Suchplan.
        settings: Modellparameter fuer den Suchagenten.

    Raises:
        ValueError: Wenn der Plan keine Suche enthaelt.

    Returns:
        Liste von Absätzen in der Reihenfolge der plan.searches.
    """

    if not plan.searches:
        raise ValueError("no searches planned")

    limiter = AsyncLimiter(max(1, MAX_CONCURRENCY), time_period=1)

    tasks = [
        asyncio.create_task(_invoke_search_model(item, settings, limiter))
        for item in plan.searches
    ]

    return await asyncio.gather(*tasks)


async def _invoke_search_model(
    item: WebSearchItem, settings: ModelSettings, limiter: AsyncLimiter
) -> str:
    """Führt den eigentlichen Modellaufruf fuer eine einzelne Suche aus."""

    client = _get_client()
    messages = [
        {
            "role": "system",
            "content": (
                "Du bist ein Heimwerker-Rechercheur. Fasse fuer die folgende Suchanfrage die wichtigsten Erkenntnisse in 2-3 Absätzen zusammen. "
                "Bleibe strikt bei DIY-Inhalten und vermeide fachfremde Hinweise."
            ),
        },
        {
            "role": "user",
            "content": f"Suchanfrage: {item.query}",
        },
    ]

    base_kwargs = settings.to_openai_kwargs()
    base_kwargs.update({"input": messages})
    base_kwargs["tools"] = [{"type": "web"}]

    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=0.5, max=2.0),
        reraise=True,
    ):
        with attempt:
            async with limiter:
                for tool_type in _collect_tool_types():
                    include_tool_choice = True
                    for _ in range(2):
                        call_kwargs = dict(base_kwargs)
                        call_kwargs["tools"] = [{"type": tool_type}]
                        if include_tool_choice:
                            call_kwargs["tool_choice"] = "auto"
                        else:
                            call_kwargs.pop("tool_choice", None)
                        metadata = dict(call_kwargs.get("metadata") or {})
                        metadata.update({"agent": "search", "query": item.query, "tool_type": tool_type})
                        call_kwargs["metadata"] = {k: str(v) for k, v in metadata.items()}
                        if OPENAI_TRACING_ENABLED:
                            call_kwargs["trace_id"] = str(uuid4())

                        _validate_payload(call_kwargs)
                        trace_input = {
                            "messages": messages,
                            "tools": [{"type": tool_type}],
                        }
                        if include_tool_choice:
                            trace_input["tool_choice"] = "auto"

                        _LOGGER.debug(
                            "Search-Payload (tool=%s, tool_choice=%s): %s",
                            tool_type,
                            "auto" if include_tool_choice else "entfernt",
                            json.dumps(
                                {k: v for k, v in call_kwargs.items() if k not in {"metadata", "trace_id"}},
                                ensure_ascii=False,
                            ),
                        )

                        try:
                            response = await asyncio.wait_for(
                                traced_completion(
                                    "search",
                                    settings.model,
                                    trace_input,
                                    lambda: client.responses.create(**call_kwargs),
                                ),
                                timeout=DEFAULT_TIMEOUT,
                            )
                            return extract_output_text(response).strip()
                        except asyncio.TimeoutError as error:
                            raise RuntimeError(f"Timeout fuer Suchanfrage '{item.query}'") from error
                        except Exception as exc:
                            if include_tool_choice and _is_tool_choice_error(exc):
                                include_tool_choice = False
                                continue
                            if _is_tool_type_error(exc, tool_type):
                                _LOGGER.warning("Tool-Typ %s wird nicht akzeptiert, versuche Fallback." , tool_type)
                                break
                            raise

    raise RuntimeError(f"search failed for query '{item.query}'")


def _is_tool_choice_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return "tool_choice" in message or "unknown parameter" in message


def _is_tool_type_error(exc: Exception, tool_type: str) -> bool:
    message = str(exc).lower()
    return tool_type.lower() in message and "supported values" in message


def _collect_tool_types() -> List[str]:
    candidates = [OPENAI_WEB_TOOL_TYPE, "web_search_preview", "web_search_preview_2025_03_11"]
    seen: List[str] = []
    for candidate in candidates:
        if candidate and candidate not in seen:
            seen.append(candidate)
    return seen


def _validate_payload(payload: dict) -> None:
    def _recurse(obj: dict, prefix: str = "") -> None:
        for key, value in obj.items():
            path = f"{prefix}.{key}" if prefix else key
            if path in _FORBIDDEN_KEYS:
                raise ValueError(
                    f"Verbotener Payload-Schluessel '{path}' erkannt. Bitte Konfiguration pruefen."
                )
            if isinstance(value, dict):
                _recurse(value, path)

    _recurse(payload)


