"""KI-gestuetzter Planner fuer DIY-Recherchen.

Das Modul orchestriert den Aufruf des OpenAI-Modells, um aus einer Anwenderfrage
strukturierte Web-Suchaufgaben abzuleiten. Dabei werden DIY-Guardrails strikt
eingehalten und jede Antwort in das `WebSearchPlan`-Schema eingepasst."""

from __future__ import annotations

import asyncio
from typing import Optional

from openai import AsyncOpenAI
from pydantic import ValidationError
from uuid import uuid4

from agents.model_settings import ModelSettings
from agents.schemas import WebSearchPlan, WebSearchItem
from config import HOW_MANY_SEARCHES, OPENAI_API_KEY, OPENAI_TRACING_ENABLED
from util.openai_tracing import traced_completion
from util import extract_output_text

_CLIENT: Optional[AsyncOpenAI] = None


def _get_client() -> AsyncOpenAI:
    """Erzeugt bei Bedarf einen wiederverwendbaren OpenAI-Client.

    Raises:
        ValueError: Wenn kein `OPENAI_API_KEY` bereitsteht.

    Returns:
        Instanz von `AsyncOpenAI`, die fuer alle Folgeaufrufe wiederverwendet wird.
    """

    global _CLIENT
    if _CLIENT is None:
        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY ist nicht gesetzt")
        _CLIENT = AsyncOpenAI(api_key=OPENAI_API_KEY)
    return _CLIENT


async def plan_searches(query: str, settings: ModelSettings) -> WebSearchPlan:
    """Leitet aus einer DIY-Anfrage konkrete Web-Suchaufgaben ab.

    Args:
        query: Urspruengliche Anwenderfrage.
        settings: Modellparameter fuer den Planner-Aufruf.

    Raises:
        ValueError: Wenn die Anfrage kein Heimwerker-Thema ist oder das Modell
            auch nach mehreren Versuchen keine gueltige JSON-Struktur liefert.

    Returns:
        Validiertes `WebSearchPlan`-Objekt mit exakt `HOW_MANY_SEARCHES` Eintraegen.
    """

    last_error: Exception | None = None
    for attempt in range(3):
        # KI-Aufruf: wir reichen Versuchszahl durch, um Prompt ggf. zu schaerfen.
        raw = await _invoke_planner_model(query, settings, attempt)
        raw = str(raw or "")

        if "REJECT" in raw.upper():
            raise ValueError("Modell hat die Anfrage als nicht-DIY abgelehnt")

        try:
            plan = WebSearchPlan.model_validate_json(raw)
        except ValidationError as error:
            last_error = error
            await asyncio.sleep(0)
            continue

        if len(plan.searches) != HOW_MANY_SEARCHES:
            last_error = ValueError("Modell lieferte eine unerwartete Anzahl von Suchanfragen")
            await asyncio.sleep(0)
            continue

        plan = _ensure_premium_slot(plan, query)
        return plan

    # Fallback: heuristische Suchaufgaben erzeugen, damit der Flow nicht blockiert.
    fallback = _heuristic_plan(query)
    if fallback:
        return _ensure_premium_slot(fallback, query)

    raise ValueError("Planner konnte keinen gueltigen WebSearchPlan erzeugen") from last_error


async def _invoke_planner_model(query: str, settings: ModelSettings, attempt: int) -> str:
    """Führt den eigentlichen OpenAI-Aufruf aus und liefert den Text-Rohoutput.

    Args:
        query: Anwenderfrage.
        settings: Modellkonfiguration.
        attempt: Laufender Versuch (0-basiert), um Prompts adaptiv anzupassen.

    Returns:
        Der rohe Text aus dem Modell, ggf. noch mit Codeblock-Prefix.
    """

    client = _get_client()
    system_prompt = (
        "Du bist ein Planer fuer Heimwerker-Recherchen. Erzeuge exakt "
        f"{HOW_MANY_SEARCHES} Suchanfragen als JSON. Felder: reason, query. "
        "Nur Heimwerker- und DIY-Themen sind zulaessig. Antworte nur mit 'REJECT', wenn das Anliegen eindeutig nicht DIY ist."
    )

    if attempt == 1:
        system_prompt += " Bedenke: Laminat verlegen, bauen, reparieren etc. sind typische DIY-Themen."
    elif attempt == 2:
        system_prompt += " Stelle sicher, dass du eine JSON-Struktur wie {'searches': [{'reason': '...', 'query': '...'}]} erzeugst."

    kwargs = settings.to_openai_kwargs()
    kwargs.update(
        {
            "input": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query},
            ]
        }
    )

    call_kwargs = dict(kwargs)
    metadata = dict(call_kwargs.get("metadata") or {})
    metadata.update({"agent": "planner", "attempt": str(attempt), "query": query})
    call_kwargs["metadata"] = {k: str(v) for k, v in metadata.items()}
    if OPENAI_TRACING_ENABLED:
        call_kwargs["trace_id"] = str(uuid4())

    # OpenAI-Aufruf mit Tracing einbetten (lokal + Plattform).
    response = await traced_completion(
        "planner",
        settings.model,
        kwargs["input"],
        lambda: client.responses.create(**call_kwargs),
    )
    output = extract_output_text(response).strip()
    # Manche Modelle geben JSON in Markdown-Codebloeken aus – Begrenzung entfernen.
    if output.startswith("```") and "```" in output[3:]:
        output = output.strip("`")
    return output


def _heuristic_plan(query: str) -> WebSearchPlan | None:
    """Erstellt eine einfache Notfall-Planung mit typischen DIY-Facetten."""

    seeds = [
        ("Materialien & Werkzeuge", f"Materialien und Werkzeuge fuer {query}"),
        ("Schritt-fuer-Schritt Anleitung", f"Anleitung {query}"),
        ("Sicherheit & Fehler vermeiden", f"Sicherheitscheck {query}"),
    ]
    items = [
        {"reason": seed_reason, "query": seed_query}
        for seed_reason, seed_query in seeds[: HOW_MANY_SEARCHES]
    ]
    try:
        return WebSearchPlan.model_validate({"searches": items})
    except ValidationError:
        return None


def _ensure_premium_slot(plan: WebSearchPlan, query: str) -> WebSearchPlan:
    """Fuegt bei Material-bezogenen Queries einen Premium-Slot hinzu."""

    keywords = {"laminat", "parkett", "material", "boden"}
    lowered = query.lower()
    if any(keyword in lowered for keyword in keywords):
        existing = {item.reason.lower() for item in plan.searches}
        premium_reason = "Premium-Optionen und Markenvergleich"
        if premium_reason.lower() not in existing:
            plan.searches.append(
                WebSearchItem(
                    reason=premium_reason,
                    query=f"Premium Laminat Markenvergleich {query}",
                )
            )
    return plan