"""Async Writer-Agent erzeugt strukturierte DIY-Berichte.

Das Modul setzt auf OpenAI, um aus Query und Recherchezusammenfassungen einen
Markdown-Report samt Kurzuebersicht und Rueckfragen zu erstellen. DIY-spezifische
Guardrails verhindern fachfremde Inhalte."""

from __future__ import annotations

import json
import re
import logging
from typing import List, Optional, Sequence

from openai import AsyncOpenAI
from pydantic import ValidationError

from agents.model_settings import ModelSettings
from agents.schemas import ReportData
from models.types import ProductItem
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
    product_results: Sequence[ProductItem] | None = None,
) -> ReportData:
    """Generiert einen strukturierten Report aus Rechercheergebnissen.

    Args:
        query: Urspruengliche Anwenderfrage.
        search_results: Liste der vom Search-Agent gelieferten Abschnitte.
        settings: Modellparameter fuer den Writer-Agenten.
        category: Optionaler Guard-Hinweis (`DIY`, `KI_CONTROL`), beeinflusst das Prompt-Template.
        product_results: Vom Search-Agent extrahierte Bauhaus-Produkte (optional).

    Raises:
        ValueError: Bei fehlenden Rechercheergebnissen.

    Returns:
        Validiertes `ReportData`-Objekt mit Kurzfassung, Markdown und Nachfragen.
    """

    if not search_results:
        raise ValueError("Keine Recherche-Ergebnisse verfuegbar")

    try:
        product_dicts = [item.model_dump() for item in (product_results or [])]
        payload = json.dumps(
            {
                "query": query,
                "search_results": search_results,
                "product_results": product_dicts,
            },
            ensure_ascii=False,
        )
        messages = _compose_messages(payload, category, product_dicts)
        raw = await _invoke_writer_model(messages, settings)

        cleaned_raw = _extract_json_block(raw)
        if len(cleaned_raw) > MAX_REPORT_LENGTH:
            cleaned_raw = cleaned_raw[: MAX_REPORT_LENGTH - len("[Gekuerzt]")] + "[Gekuerzt]"

        report = ReportData.model_validate_json(cleaned_raw)
        report.markdown_report = _inject_product_section(
            report.markdown_report,
            list(product_results or []),
        )
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
        "writer_email",
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


def _compose_messages(
    payload: str,
    category: str | None,
    product_results: Optional[List[dict]],
) -> list[dict[str, str]]:
    """Erstellt die Prompts fuer den Writer basierend auf der Kategorie."""

    if category == "KI_CONTROL":
        system_prompt = (
            "Du bist ein KI-Governance-Analyst. Erstelle einen strukturierten Markdown-Report zur Steuerung und Evaluierung von KI-Agenten im Heimwerker-Kontext. "
            "Pflichtabschnitte: 1) Ziel & Kontext, 2) Steuerbare Aspekte (Tools, Prompts, Guardrails), 3) Risiken & Mitigations, 4) Metriken (Halluzination, Coverage, Freshness), "
            "5) Evaluationsplan (Testfaelle, Akzeptanzkriterien), 6) Governance (Freigaben, Logging, Tracing), 7) Empfehlungen & Roadmap, 8) FAQ. "
            "Nutze sachliches Deutsch, klare Listen, Tabellen und Hervorhebungen. Antworte ausschließlich mit JSON (short_summary, markdown_report, followup_questions mit 4-6 Fragen)."
        )
    else:
        product_hint = (
            "Dir stehen strukturierte Bauhaus-Produktdaten unter 'product_results' zur Verfügung. Verwende sie ausschliesslich für die Sektion '## Einkaufsliste (Bauhaus-Links)' und erfinde keine weiteren Links."
            if product_results
            else "Falls 'product_results' leer ist, schreibe unter '## Einkaufsliste (Bauhaus-Links)' nur einen kurzen Hinweis, dass keine geprüften Bauhaus-Produkte gefunden wurden."
        )
        system_prompt = (
            "Du bist ein Heimwerker-Technikautor fuer Premium-Projekte. Erstelle einen ausfuehrlichen Markdown-Report (mindestens 1.800 bis 2.500 Woerter) in sachlichem Deutsch. "
            "Struktur strikt einhalten:\n"
            "1. H1-Projekttitel.\n"
            "2. Meta-Zeile im Format '> **Meta:** Niveau Anfänger · Zeit 14–18 h · Budget 250–450 €' (Werte anpassen, falls Query oder product_results andere Angaben liefern; sonst Defaults nutzen).\n"
            "3. Abschnitt '## Inhaltsverzeichnis' mit einer ungeordneten Liste aus Markdown-Links. Jede Zeile: '- [Titel](#kebab-case-anchor)'. Nur interne Anker mit kleingeschriebenen, bindestrich-getrennten IDs. Keine externen Links.\n"
            "4. '## Vorbereitung' – Voraussetzungen, Werkzeuge vorbereiten, Sicherheits-Hinweise.\n"
            "5. '## Einkaufsliste (Bauhaus-Links)' – Liste, die ausschließlich auf den gelieferten product_results basiert. Keine Platzhalter-Links erfinden.\n"
            "6. '## Schritt-für-Schritt' – Nummerierte Liste. Jeder Schritt endet mit einer separaten Zeile '**Prüfkriterium:** ...' (konkret messbar).\n"
            "7. '## Qualität & Sicherheit' – Checks, PSA, Belüftung, Entsorgung.\n"
            "8. '## Zeit & Kosten' – Tabelle mit Arbeitspaketen, Dauer, Kosten inkl. Puffer.\n"
            "9. Optional '## Optionen & Upgrades' – nur wenn sinnvolle Erweiterungen (z. B. Kleiderstange, Soft-Close) existieren.\n"
            "10. Optional '## Pflege & Wartung' – nur wenn relevante Hinweise vorhanden sind.\n"
            "11. '## FAQ' – 3–5 kurze Fragen & Antworten.\n"
            f"{product_hint} Nutze Listen, Tabellen, Hinweis-Blockquotes sauber. Keine spaeteren Laminat-Abschnitte. "
            "Stelle sicher, dass alle H2/H3-Überschriften in kebab-case referenzierbar sind und keine externen Links im Inhaltsverzeichnis erscheinen. "
            "Gib am Ende 4-6 passende Nachfragen zurück. Antworte ausschließlich als JSON-Objekt mit short_summary, markdown_report, followup_questions."
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


def _inject_product_section(markdown: str, products: List[ProductItem]) -> str:
    section_header = "## Einkaufsliste (Bauhaus-Links)"

    lines: List[str] = []
    if products:
        for item in products:
            price = (item.price_text or "ca. Preis auf Anfrage").strip()
            note = (item.note or "").strip()
            parts = [f"[{item.title}]({item.url})"]
            if note:
                parts.append(note)
            if price:
                parts.append(price)
            lines.append("- " + " – ".join(parts))
    else:
        lines.append("- Keine geprüften Bauhaus-Produkte verfügbar.")

    replacement = section_header + "\n\n" + "\n".join(lines) + "\n\n"

    pattern = re.compile(
        r"##\s+einkaufsliste[\s\S]*?(?=\n##\s+|\Z)",
        re.IGNORECASE,
    )
    if pattern.search(markdown):
        return pattern.sub(replacement, markdown).strip()

    # Falls Abschnitt fehlt, direkt nach Vorbereitung einfügen
    prep_match = re.search(r"##\s+vorbereitung[\s\S]*?(?=\n##\s+|\Z)", markdown, re.IGNORECASE)
    if prep_match:
        insert_at = prep_match.end()
        return (markdown[:insert_at] + "\n\n" + replacement + markdown[insert_at:]).strip()

    return (markdown.strip() + "\n\n" + replacement).strip()


