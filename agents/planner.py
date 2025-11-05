"""KI-gestützter Planner für Home-Task-AI-Projekte.

Dieses Modul übersetzt eine Nutzerfrage in strukturierte Web-Recherchen. Dabei
arbeiten wir ausschließlich in DIY-konformen Grenzen und brauchen deshalb eine
enge Kontrolle über Prompt, Validierung und Fallbacks. Die Klasse `_invoke_planner_model`
ist der zentrale Berührungspunkt zum OpenAI-Backend; `plan_searches` kümmert sich
um Wiederholversuche, strikte JSON-Validierung sowie ein Heuristik-Fallback, damit
der Gesamtfluss nicht blockiert, falls das Modell doch einmal ausfällt."""

from __future__ import annotations

import asyncio
from typing import Optional

from openai import AsyncOpenAI
from pydantic import ValidationError
from uuid import uuid4

from agents.model_settings import ModelSettings
from agents.schemas import WebSearchPlan, WebSearchItem, SearchPhase
from config import HOW_MANY_SEARCHES, OPENAI_API_KEY, OPENAI_TRACING_ENABLED
from util.openai_tracing import traced_completion
from util import extract_output_text

_CLIENT: Optional[AsyncOpenAI] = None


def _get_client() -> AsyncOpenAI:
    """Erzeugt bei Bedarf einen wiederverwendbaren OpenAI-Client.

    Hintergrund: Wir verwenden einen globalen Client, damit TCP-Verbindungen
    und TLS-Handshakes wiederverwendet werden. Das ist performanter und verhindert
    Rate-Limit-Probleme, die durch zu viele parallel aufgebaute Sessions entstehen.

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
        # Wir lassen dem Modell bis zu drei Versuche, auch wenn z. B. JSON-Parsing
        # fehlschlägt. Je Versuch verschärfen wir den Prompt, damit die KI lernt,
        # worauf es ankommt (siehe `_invoke_planner_model`).
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

        if not (1 <= len(plan.searches) <= 10):
            last_error = ValueError("Modell lieferte außerhalb des 1..10 Bereichs")
            await asyncio.sleep(0)
            continue

        if any(not item.query.strip() for item in plan.searches):
            last_error = ValueError("Mindestens eine query ist leer")
            await asyncio.sleep(0)
            continue

        plan = _ensure_premium_slot(plan, query)

        if len(plan.searches) > 10:
            last_error = ValueError("Plan überschreitet 10 Einträge nach Premium-Slot")
            await asyncio.sleep(0)
            continue

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
    system_prompt_template = """Du bist ein Recherche-Planner für Heimwerkerprojekte. Plane für \"{QUERY}\" fünf bis acht präzise Web-Suchaufgaben.\n"
    "Antworte ausschließlich mit gültigem JSON (kein Markdown, keine Erklärungen):\n"
    "{{\n"
    "  \"searches\": [\n"
    "    {{ \"reason\": \"<Phase>\", \"query\": \"<Suchtext ohne Floskeln>\" }}\n"
    "  ]\n"
    "}}\n\n"
    "Phasen (verwende jeden höchstens einmal, exakt diese Bezeichner):\n"
    "\"Vorbereitung & Planung\",\"Material & Werkzeuge\",\"Sicherheit & Umwelt\",\"Ausführung Schritt-für-Schritt\",\"Qualität & Kontrolle\",\"Zeit & Kosten\",\"Optionen & Upgrades\",\"Pflege & Wartung\",\"Demontage/Untergrund\",\"Visual Guide\"\n\n"
    "Regeln:\n"
    "- Liefere 5–8 Einträge; wähle nur Phasen, die zu \"{QUERY}\" passen, ohne Duplikate.\n"
    "- Formuliere jede query als dichte Stichwortkette mit 5–9 Segmenten (z. B. Untergrund, Maße, Reihenfolge, Trocknungszeiten, Prüf-Kriterien, Markenvergleich, Budget, Ablauf).\n"
    "- Keine Fragen, keine Füllwörter, keine externen Domains oder Floskeln.\n"
    "- Mindestens eine Aufgabe muss klare Dauer- oder Kostenbegriffe enthalten (Phase \"Zeit & Kosten\").\n"
    "- Wenn das Thema nicht DIY-tauglich ist, antworte exakt mit \"REJECT\".\n\n"
    "Beispiel:\n"
    "{{\n"
    "  \"searches\": [\n"
    "    {{ \"reason\": \"Vorbereitung & Planung\", \"query\": \"{QUERY} Vorbereitung: Untergrundprüfung, Maßaufnahme, Werkzeug-Setup, Abdeckplan, Materiallogistik, Prioritäten\" }},\n"
    "    {{ \"reason\": \"Material & Werkzeuge\", \"query\": \"Materialliste {QUERY}: Kernmaterialien, Zubehör, Mengenrechner, Qualitätsstufen, Bauhaus-Verfügbarkeit, Preis-Leistung\" }},\n"
    "    {{ \"reason\": \"Zeit & Kosten\", \"query\": \"Zeit & Kosten {QUERY}: Arbeitspakete, Dauer je Schritt, Kostenrahmen, Pufferzeiten, Mietgeräte, Lieferfristen\" }}\n"
    "  ]\n"
    "}}"""

    system_prompt = system_prompt_template.replace("{QUERY}", query)

    if attempt == 1:
        system_prompt += (
            "\n\nHinweis: Vorherige Antwort war ungültig. Antworte diesmal mit gültigem JSON, 5–8 Einträgen und eindeutigen Phasen."
        )
    elif attempt == 2:
        system_prompt += (
            "\n\nLetzte Warnung: Erstes Zeichen muss '{' sein. Benutze jede Phase höchstens einmal und liefere 5–8 präzise Stichwort-Queries."
        )

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
    # Hinweis: Wir verzichten bewusst auf ein `trace_id`-Feld, weil die aktuelle
    # OpenAI Responses-API diesen Parameter nicht akzeptiert. Tracing aktiviert
    # dennoch `util.openai_tracing` automatisch über Umgebungssvariablen.

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
    """Erstellt eine einfache Notfall-Planung mit typischen DIY-Facetten.

    Diese Funktion springt ein, wenn das LLM dreimal scheitert. Wir geben der Pipeline
    dann trotzdem drei gut bekannte Suchfacetten mit, damit der Flow nicht komplett
    abbricht (lieber heuristisch als gar nicht)."""

    seeds: list[tuple[SearchPhase, str]] = [
        (
            SearchPhase.VORBEREITUNG_PLANUNG,
            f"{query} Vorbereitung: Untergrund, Maße, Zeitplan, Raumlogistik, Werkzeugbedarf, Reihenfolge",
        ),
        (
            SearchPhase.MATERIAL_WERKZEUGE,
            f"{query} Materialliste: Hauptmaterialien, Zubehör, Mengenplanung, Qualitätsstufen, Bezugsquellen, Preisrahmen",
        ),
        (
            SearchPhase.SICHERHEIT_UMWELT,
            f"{query} Sicherheit: PSA, Gefahren, Lüftung, Strom/Wasser-Zonen, Entsorgung, typische Fehler vermeiden",
        ),
    ]
    items = [
        {
            "reason": seed_reason.value,
            "query": seed_query,
        }
        for seed_reason, seed_query in seeds[: HOW_MANY_SEARCHES]
    ]
    try:
        return WebSearchPlan.model_validate({"searches": items})
    except ValidationError:
        return None


def _ensure_premium_slot(plan: WebSearchPlan, query: str) -> WebSearchPlan:
    """Fuegt bei Material-bezogenen Queries einen Premium-Slot hinzu.

    Für bestimmte Suchbegriffe (z. B. Laminat) brauchen wir einen zusätzlichen Slot,
    damit nach Premium-/Markenoptionen gesucht wird. Wir ergänzen ihn nur, wenn die
    Liste bislang keinen entsprechenden Eintrag enthält."""

    keywords = {"laminat", "parkett", "material", "boden"}
    lowered = query.lower()
    if (
        any(keyword in lowered for keyword in keywords)
        and all(item.reason != SearchPhase.OPTIONEN_UPGRADES for item in plan.searches)
        and len(plan.searches) < 10
    ):
        plan.searches.append(
            WebSearchItem(
                reason=SearchPhase.OPTIONEN_UPGRADES,
                query=f"Optionen & Upgrades {query}: Produktalternativen, Premiumoberflächen, Zusatzfeatures, Garantien, Zusatzkosten, Markenvergleich, Kompatibilität, Nachhaltigkeit",
            )
        )
    return plan