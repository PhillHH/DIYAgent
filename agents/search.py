"""Async-Implementierung fuer Web-Suchoperationen mit OpenAI."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import List, Optional, Sequence, Tuple

from aiolimiter import AsyncLimiter
from openai import AsyncOpenAI
from tenacity import AsyncRetrying, RetryError, stop_after_attempt, wait_exponential_jitter
from uuid import uuid4

from agents.model_settings import ModelSettings
from agents.schemas import WebSearchItem, WebSearchPlan
from models.types import ProductItem
from pydantic import ValidationError
from config import (
    DEFAULT_TIMEOUT,
    MAX_CONCURRENCY,
    OPENAI_API_KEY,
    OPENAI_TRACING_ENABLED,
    OPENAI_WEB_TOOL_TYPE,
)
from util.openai_tracing import traced_completion
from util.url_sanitizer import clean_product_url
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


async def perform_searches(
    plan: WebSearchPlan,
    settings: ModelSettings,
    *,
    user_query: str,
    category: str | None = None,
) -> Tuple[List[str], List[ProductItem]]:
    """Generiert fuer jede geplante Suche eine Kurz-Zusammenfassung.

    Args:
        plan: Vom Planner erzeugter Suchplan.
        settings: Modellparameter fuer den Suchagenten.

    Raises:
        ValueError: Wenn der Plan keine Suche enthaelt.

    Returns:
        Tupel aus Liste der Zusammenfassungen und Bauhaus-Produktdaten.
    """

    if not plan.searches:
        raise ValueError("no searches planned")

    if (category or "").upper() == "DIY":
        bauhaus_reason = "Einkaufsliste Bauhaus"
        bauhaus_query = (
            f"{user_query} benötigte Produkte und Zubehör site:bauhaus.info OR site:bauhaus.at OR site:bauhaus.de"
        )
        exists = any(
            item.reason == bauhaus_reason and "site:bauhaus" in item.query.lower()
            for item in plan.searches
        )
        if not exists:
            plan.searches.append(
                WebSearchItem(reason=bauhaus_reason, query=bauhaus_query)
            )

    limiter = AsyncLimiter(max(1, MAX_CONCURRENCY), time_period=1)

    tasks = [
        asyncio.create_task(_execute_search_item(item, settings, limiter))
        for item in plan.searches
    ]

    combined = await asyncio.gather(*tasks)
    summaries: List[str] = []
    product_results: List[ProductItem] = []

    for summary, products in combined:
        if summary:
            summaries.append(summary)
        if products:
            product_results.extend(products)

    return summaries, product_results


async def _execute_search_item(
    item: WebSearchItem, settings: ModelSettings, limiter: AsyncLimiter
) -> Tuple[str, List[ProductItem]]:
    if _is_product_search(item):
        return await _invoke_product_search(item, settings, limiter)
    summary = await _invoke_standard_search(item, settings, limiter)
    return summary, []


async def _invoke_standard_search(
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


async def _invoke_product_search(
    item: WebSearchItem, settings: ModelSettings, limiter: AsyncLimiter
) -> Tuple[str, List[ProductItem]]:
    client = _get_client()
    messages = [
        {
            "role": "system",
            "content": (
                "Du bist ein Rechercheur und erstellst eine Einkaufsliste für Bauhaus-Produkte. Du MUSST das Web-Tool verwenden und ausschließlich Produkte von bauhaus.info, bauhaus.at oder bauhaus.de extrahieren. "
                'Antwortformat: {"items": [{"title": "string", "url": "string", "note": "string|null", "price_text": "string|null"}]}'
            ),
        },
        {
            "role": "user",
            "content": (
                f"Suche nach Produkten und Zubehör für: {item.query}. "
                "Gib mindestens drei relevante Produkte an, falls verfügbar, und entferne Affiliate-/Tracking-Parameter."
            ),
        },
    ]

    base_kwargs = settings.to_openai_kwargs()
    base_kwargs.update({"input": messages})
    base_kwargs["tools"] = [{"type": "web"}]
    base_kwargs["response_format"] = {
        "type": "json_schema",
        "json_schema": {
            "name": "BauhausProducts",
            "schema": {
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "url": {"type": "string"},
                                "note": {"type": "string"},
                                "price_text": {"type": "string"},
                            },
                            "required": ["title", "url"],
                            "additionalProperties": False,
                        },
                    }
                },
                "required": ["items"],
                "additionalProperties": False,
            },
        },
    }

    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=0.5, max=2.0),
        reraise=True,
    ):
        with attempt:
            async with limiter:
                for tool_type in _collect_tool_types():
                    include_tool_choice = True
                    call_kwargs_base = dict(base_kwargs)
                    call_kwargs_base["tools"] = [{"type": tool_type}]
                    metadata = dict(call_kwargs_base.get("metadata") or {})
                    metadata.update(
                        {
                            "agent": "search_products",
                            "query": item.query,
                            "tool_type": tool_type,
                        }
                    )
                    call_kwargs_base["metadata"] = {k: str(v) for k, v in metadata.items()}
                    if OPENAI_TRACING_ENABLED:
                        call_kwargs_base["trace_id"] = str(uuid4())

                    for _ in range(2):
                        call_kwargs = dict(call_kwargs_base)
                        if include_tool_choice:
                            call_kwargs["tool_choice"] = "auto"
                        else:
                            call_kwargs.pop("tool_choice", None)

                        _validate_payload(call_kwargs)
                        trace_payload = {
                            "messages": messages,
                            "tools": [{"type": tool_type}],
                            "query": item.query,
                        }

                        parse_attempts = 0
                        while parse_attempts < 2:
                            parse_attempts += 1
                            try:
                                response = await asyncio.wait_for(
                                    traced_completion(
                                        "search_products",
                                        settings.model,
                                        trace_payload,
                                        lambda: client.responses.create(**call_kwargs),
                                    ),
                                    timeout=DEFAULT_TIMEOUT,
                                )
                            except asyncio.TimeoutError as error:
                                raise RuntimeError(
                                    f"Timeout fuer Produkt-Suchanfrage '{item.query}'"
                                ) from error
                            except Exception as exc:
                                if include_tool_choice and _is_tool_choice_error(exc):
                                    include_tool_choice = False
                                    break
                                if _is_tool_type_error(exc, tool_type):
                                    _LOGGER.warning(
                                        "Tool-Typ %s wird nicht akzeptiert (Produkte), versuche Fallback.",
                                        tool_type,
                                    )
                                    break
                                _LOGGER.warning("Produkt-Suche fehlgeschlagen: %s", exc)
                                return "Einkaufsliste Bauhaus: Fehler bei der Produktsuche.", []

                            raw_text = extract_output_text(response).strip()
                            try:
                                products = _parse_product_response(raw_text)
                                summary = (
                                    f"Einkaufsliste Bauhaus: {len(products)} Produkte extrahiert."
                                    if products
                                    else "Einkaufsliste Bauhaus: keine Produkte gefunden."
                                )
                                return summary, products
                            except ValueError as parse_error:
                                if parse_attempts < 2:
                                    _LOGGER.warning(
                                        "Produkt-Antwort ungueltig (%s) – erneuter Versuch.",
                                        parse_error,
                                    )
                                    continue
                                _LOGGER.warning(
                                    "Produkt-JSON nach Wiederholungsversuch ungueltig: %s",
                                    raw_text[:160],
                                )
                                return "Einkaufsliste Bauhaus: keine Produkte gefunden.", []

                        if not include_tool_choice:
                            continue
                        break

                    if include_tool_choice:
                        break

    return "Einkaufsliste Bauhaus: keine Ergebnisse.", []


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


def _is_product_search(item: WebSearchItem) -> bool:
    haystack = f"{item.reason} {item.query}".lower()
    return "einkaufsliste" in haystack and "bauhaus" in haystack


def _parse_product_response(text: str) -> List[ProductItem]:
    if not text or not text.strip():
        raise ValueError("leere Produktantwort")

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        try:
            data = json.loads(_extract_json_block(text))
        except json.JSONDecodeError as exc:
            raise ValueError("Produkt-JSON konnte nicht gelesen werden") from exc

    if isinstance(data, dict):
        items: Sequence[dict] = data.get("items") or data.get("products") or []
    elif isinstance(data, list):
        items = data  # type: ignore[assignment]
    else:
        items = []

    products: List[ProductItem] = []
    for raw in items:
        if not isinstance(raw, dict):
            continue
        title = (raw.get("title") or raw.get("name") or "").strip()
        url_raw = (raw.get("url") or raw.get("link") or "").strip()
        if not title or not url_raw:
            continue
        try:
            sanitized_url = clean_product_url(url_raw)
        except ValueError:
            continue

        note = (raw.get("note") or raw.get("description") or "").strip() or None
        price = (
            raw.get("price_text")
            or raw.get("price")
            or raw.get("price_eur")
            or raw.get("cost")
            or ""
        )
        price = price.strip() or None

        try:
            product = ProductItem.model_validate(
                {
                    "title": title,
                    "url": sanitized_url,
                    "note": note,
                    "price_text": price,
                }
            )
        except ValidationError as exc:
            _LOGGER.debug("Produkt verworfen (Validierungsfehler): %s", exc)
            continue
        products.append(product)

    return products


def _extract_json_block(text: str) -> str:
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    if fence:
        candidate = fence.group(1).strip()
        if candidate.startswith("{") and candidate.endswith("}"):
            return candidate

    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped

    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        return match.group(0)

    return text


