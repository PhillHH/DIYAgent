"""Async Writer-Agent erzeugt strukturierte DIY-Berichte.

Das Modul setzt auf OpenAI, um aus Query und Recherchezusammenfassungen einen
Markdown-Report samt Kurzuebersicht und Rueckfragen zu erstellen. DIY-spezifische
Guardrails verhindern fachfremde Inhalte."""

from __future__ import annotations

import json
import re
import logging
from typing import List, Optional

from openai import AsyncOpenAI
from pydantic import ValidationError

from agents.model_settings import ModelSettings
from agents.schemas import ReportData
from config import OPENAI_API_KEY, OPENAI_TRACING_ENABLED
from util.openai_tracing import traced_completion
from util import extract_output_text

MAX_REPORT_LENGTH = 40_000
_CLIENT: Optional[AsyncOpenAI] = None
_LOGGER = logging.getLogger(__name__)


def _get_client() -> AsyncOpenAI:
    """Stellt einen wiederverwendbaren OpenAI-Client bereit.

    Raises:
        ValueError: Wenn kein `OPENAI_API_KEY` konfiguriert ist.

    Returns:
        Instanz von `AsyncOpenAI` fuer wiederholte Aufrufe.
    """

    global _CLIENT
    if _CLIENT is None:
        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY ist nicht gesetzt")
        _CLIENT = AsyncOpenAI(api_key=OPENAI_API_KEY)
    return _CLIENT


async def write_report(
    query: str,
    search_results: List[str],
    settings: ModelSettings,
    category: str | None = None,
) -> ReportData:
    """Generiert einen strukturierten Report aus Rechercheergebnissen.

    Args:
        query: Urspruengliche Anwenderfrage.
        search_results: Liste der vom Search-Agent gelieferten Abschnitte.
        settings: Modellparameter fuer den Writer-Agenten.
        category: Optionaler Guard-Hinweis (`DIY`, `KI_CONTROL`), beeinflusst das Prompt-Template.

    Raises:
        ValueError: Bei fehlenden Rechercheergebnissen.

    Returns:
        Validiertes `ReportData`-Objekt mit Kurzfassung, Markdown und Nachfragen.
    """

    if not search_results:
        raise ValueError("Keine Recherche-Ergebnisse verfuegbar")

    try:
        payload = json.dumps({"query": query, "search_results": search_results})
        messages = _compose_messages(payload, category)
        raw = await _invoke_writer_model(messages, settings)

        cleaned_raw = _extract_json_block(raw)
        if len(cleaned_raw) > MAX_REPORT_LENGTH:
            cleaned_raw = cleaned_raw[: MAX_REPORT_LENGTH - len("[Gekuerzt]")] + "[Gekuerzt]"

        report = ReportData.model_validate_json(cleaned_raw)
        return report
    except Exception as exc:  # pragma: no cover - Fehlerpfad fuer Diagnose
        _LOGGER.exception("Writer fehlgeschlagen: %s", exc)
        raise


async def _invoke_writer_model(messages: list[dict[str, str]], settings: ModelSettings) -> str:
    """Ruft das Reporterzeugende Modell auf und gibt einen JSON-String zurueck.

    Args:
        payload: JSON-String mit Query und Suchergebnissen.
        settings: Modellkonfiguration fuer den Writer.

    Returns:
        Rohantwort des Modells als String, bereinigt von Codeblock-Markup.
    """

    client = _get_client()

    kwargs = settings.to_openai_kwargs()
    chat_kwargs = {
        "model": kwargs.get("model", settings.model),
        "messages": messages,
        "temperature": kwargs.get("temperature", 0.2),
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "PremiumReport",
                "schema": {
                    "type": "object",
                    "properties": {
                        "short_summary": {"type": "string"},
                        "markdown_report": {"type": "string"},
                        "followup_questions": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 4,
                            "maxItems": 6,
                        },
                    },
                    "required": ["short_summary", "markdown_report", "followup_questions"],
                    "additionalProperties": False,
                },
            },
        },
    }
    if kwargs.get("max_tokens") is not None:
        chat_kwargs["max_tokens"] = kwargs["max_tokens"]

    call_kwargs = dict(chat_kwargs)

    response = await traced_completion(
        "writer",
        settings.model,
        {"messages": messages},
        lambda: client.chat.completions.create(**call_kwargs),
    )
    _LOGGER.debug("Writer response type=%s", type(response))
    output = extract_output_text(response).strip()
    return _extract_json_block(output)


def _extract_json_block(text: str) -> str:
    """Extrahiert den JSON-Block aus einer modellierten Antwort."""

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

    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        return text[first_brace : last_brace + 1]

    stripped = text.strip()
    if stripped.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z0-9_]*\n", "", stripped)
        cleaned = re.sub(r"```$", "", cleaned.strip())
        return cleaned

    return text


def _compose_messages(payload: str, category: str | None) -> list[dict[str, str]]:
    """Erstellt die Prompts fuer den Writer basierend auf der Kategorie."""

    if category == "KI_CONTROL":
        system_prompt = (
            "Du bist ein KI-Governance-Analyst. Erstelle einen strukturierten Markdown-Report zur Steuerung und Evaluierung von KI-Agenten im Heimwerker-Kontext. "
            "Pflichtabschnitte: 1) Ziel & Kontext, 2) Steuerbare Aspekte (Tools, Prompts, Guardrails), 3) Risiken & Mitigations, 4) Metriken (Halluzination, Coverage, Freshness), "
            "5) Evaluationsplan (Testfaelle, Akzeptanzkriterien), 6) Governance (Freigaben, Logging, Tracing), 7) Empfehlungen & Roadmap, 8) FAQ. "
            "Nutze sachliches Deutsch, klare Listen, Tabellen und Hervorhebungen. Antworte ausschließlich mit JSON (short_summary, markdown_report, followup_questions mit 4-6 Fragen)."
        )
    else:
        system_prompt = (
            "Du bist ein Heimwerker-Technikautor fuer Premium-Projekte. Erstelle einen ausfuehrlichen Markdown-Report (mindestens 1.800 bis 2.500 Woerter) mit folgenden Abschnitten: "
            "1) H1-Projekttitel, 2) Executive Summary (5-7 Saetze), 3) Projektueberblick & Voraussetzungen, 4) Tabelle 'Material & Werkzeuge' mit Spalten Position, Spezifikation, Menge, Stueckpreis, Summe, "
            "5) Schritt-fuer-Schritt-Anleitung (nummeriert, detailreich), 6) Zeit- & Kostenplan (Tabelle mit Puffer), 7) Qualitaetssicherung & typische Fehler, 8) Sicherheit (Schutz, Lueftung, Entsorgung), "
            "9) Abschnitt 'Premium-Laminat' mit 3-5 kuratierten Optionen (Nutzungsklasse, Abriebklasse, Staerke, Klicksystem, Garantie, Preisspannen), 10) Pflege & Wartung, 11) FAQ. "
            "Nutze klares Deutsch, sinnvolle Zwischenueberschriften (H2/H3), Tabellen, Listen und Zitat-Bloecke fuer Hinweise. Folge Fragen: Liefere 4-6 passende Nachfragen. "
            "Antworte ausschließlich mit einem JSON-Objekt (kein Text davor oder danach) mit den Feldern short_summary, markdown_report, followup_questions."
        )

    return [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": (
                "Hier sind Anfrage und Zusammenfassungen als JSON:\n"
                f"{payload}"
            ),
        },
    ]


