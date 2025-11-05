"""Writer-Agent erzeugt strukturierte Projektberichte fuer Home Task AI.

Der Writer nutzt OpenAI, um auf Basis von Planner/Search-Ergebnissen einen
vollstaendigen DIY-Report zu erstellen. Neu wird ein `ReportPayload` erzeugt,
das der Emailer spaeter ohne Markdown-Parsing wiederverwenden kann. Markdown
wird ueber ein Jinja2-Template gerendert, wodurch Layout und Copy konsistent
bleiben."""

from __future__ import annotations

import json
import logging
import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from jinja2 import Environment, FileSystemLoader, Template, select_autoescape
from openai import AsyncOpenAI
from pydantic import ValidationError

from agents.model_settings import ModelSettings
from agents.schemas import ReportData
from config import OPENAI_API_KEY
from models.report_payload import (
    NarrativeSection,
    ReportMeta,
    ReportPayload,
    ReportTOCEntry,
    ShoppingItem,
    ShoppingList,
    StepDetail,
    StepsSection,
    TimeCostRow,
    TimeCostSection,
)
from models.types import ProductItem
from util import extract_output_text
from util.openai_tracing import traced_completion
from util.url_sanitizer import clean_product_url

MAX_REPORT_LENGTH = 80_000
_CLIENT: Optional[AsyncOpenAI] = None
_LOGGER = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
_JINJA_ENV = Environment(
    loader=FileSystemLoader(_TEMPLATE_DIR),
    autoescape=select_autoescape(disabled_extensions=("md.j2",)),
    trim_blocks=True,
    lstrip_blocks=True,
)
_REPORT_TEMPLATE_NAME = "report.md.j2"


def _build_response_schema() -> Dict[str, Any]:
    schema = deepcopy(ReportPayload.model_json_schema())
    defs = schema.pop("$defs", None)
    schema.pop("title", None)

    top_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "short_summary": {"type": "string"},
            "report_payload": schema,
            "followup_questions": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 4,
                "maxItems": 6,
            },
        },
        "required": ["short_summary", "report_payload", "followup_questions"],
        "additionalProperties": False,
    }
    if defs:
        top_schema["$defs"] = defs
    return top_schema


_REPORT_RESPONSE_SCHEMA = _build_response_schema()


def _get_client() -> AsyncOpenAI:
    """Stellt einen wiederverwendbaren OpenAI-Client bereit."""

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
    """Generiert einen strukturierten Report aus Rechercheergebnissen."""

    if not search_results:
        raise ValueError("Keine Recherche-Ergebnisse verfuegbar")

    if category == "KI_CONTROL":
        return await _write_ki_control_report(query, search_results, settings)

    return await _write_diy_report(query, search_results, settings, product_results or [])


async def _write_diy_report(
    query: str,
    search_results: List[str],
    settings: ModelSettings,
    product_results: Sequence[ProductItem],
) -> ReportData:
    product_payload = [
        {
            "id": index,
            "title": item.title,
            "url": str(item.url),
            "note": item.note,
            "price_text": item.price_text,
        }
        for index, item in enumerate(product_results, start=1)
    ]

    payload_json = json.dumps(
        {
            "query": query,
            "search_results": search_results,
            "product_results": product_payload,
        },
        ensure_ascii=False,
    )

    messages = _compose_messages_diy(payload_json, query, product_payload)
    raw = await _invoke_writer_model(messages, settings, schema=_REPORT_RESPONSE_SCHEMA)

    cleaned = _extract_json_block(raw)
    try:
        response = json.loads(cleaned)
    except json.JSONDecodeError as exc:  # pragma: no cover - Diagnosepfad
        raise ValueError("Writer lieferte kein gueltiges JSON") from exc

    try:
        structured = ReportPayload.model_validate(response["report_payload"])
    except (KeyError, ValidationError) as exc:
        raise ValueError("Writer lieferte kein gueltiges ReportPayload") from exc

    followups = response.get("followup_questions", [])
    short_summary = (response.get("short_summary") or "").strip()

    structured = _postprocess_payload(structured, product_results)
    followups = _normalize_followups(followups or structured.followups)
    structured.followups = followups
    structured.toc = _build_toc(structured)
    structured.meta = _ensure_meta(structured)

    markdown_report = _render_markdown(structured)
    if len(markdown_report) > MAX_REPORT_LENGTH:
        markdown_report = markdown_report[: MAX_REPORT_LENGTH - len("[Gekuerzt]")] + "[Gekuerzt]"

    if not short_summary:
        teaser_first_line = structured.teaser.splitlines()[0] if structured.teaser else ""
        short_summary = teaser_first_line.strip() or structured.title[:120]

    return ReportData(
        short_summary=short_summary,
        markdown_report=markdown_report,
        followup_questions=followups,
        payload=structured,
    )


async def _write_ki_control_report(
    query: str,
    search_results: List[str],
    settings: ModelSettings,
) -> ReportData:
    payload_json = json.dumps(
        {
            "query": query,
            "search_results": search_results,
        },
        ensure_ascii=False,
    )

    messages = _compose_messages_ki_control(payload_json)
    raw = await _invoke_writer_model(messages, settings)
    cleaned = _extract_json_block(raw)
    report = ReportData.model_validate_json(cleaned)
    return report


def _postprocess_payload(payload: ReportPayload, products: Sequence[ProductItem]) -> ReportPayload:
    updated = payload.model_copy(deep=True)
    updated.shopping_list = _merge_product_results(updated.shopping_list, products)
    updated.followups = _normalize_followups(updated.followups)
    return updated


def _merge_product_results(shopping: ShoppingList, products: Sequence[ProductItem]) -> ShoppingList:
    merged = shopping.model_copy(deep=True)
    existing_by_url: Dict[str, ShoppingItem] = {}
    for item in merged.items:
        if item.url:
            try:
                sanitized = clean_product_url(str(item.url))
            except ValueError:
                sanitized = str(item.url)
            existing_by_url[sanitized] = item

    final_items: List[ShoppingItem] = []
    used_urls: set[str] = set()

    for idx, product in enumerate(products, start=1):
        try:
            sanitized_url = clean_product_url(str(product.url))
        except ValueError:
            sanitized_url = str(product.url)

        existing = existing_by_url.get(sanitized_url)
        price_text = (product.price_text or (existing.price if existing else None) or "ca. Preis auf Anfrage").strip()
        rationale = existing.rationale if existing else (product.note or "Empfohlenes Bauhaus-Produkt")
        quantity = existing.quantity if existing else "1"
        category = existing.category if existing else "Material"
        product_name = existing.product if existing else product.title

        final_items.append(
            ShoppingItem(
                position=existing.position or idx if existing else idx,
                category=category,
                product=product_name,
                quantity=quantity,
                rationale=rationale,
                price=price_text,
                url=sanitized_url,
            )
        )
        used_urls.add(sanitized_url)

    for item in merged.items:
        if not item.url:
            final_items.append(item)
            continue
        try:
            sanitized = clean_product_url(str(item.url))
        except ValueError:
            sanitized = str(item.url)
        if sanitized in used_urls:
            continue
        final_items.append(item)

    deduped: List[ShoppingItem] = []
    seen_categories: set[str] = set()
    for item in final_items:
        category_key = (item.category or "").strip().lower()
        if category_key in seen_categories:
            continue
        seen_categories.add(category_key)
        deduped.append(item)

    merged.items = deduped
    return merged


def _normalize_followups(items: Sequence[str]) -> List[str]:
    normalized: List[str] = []
    for entry in items:
        text = (entry or "").strip()
        if not text:
            continue
        if not text.lower().startswith("als nächstes"):
            text = f"Als Nächstes: {text}"
        normalized.append(text)
    return normalized[:6]


def _build_toc(payload: ReportPayload) -> List[ReportTOCEntry]:
    entries: List[ReportTOCEntry] = []

    def add(title: str, level: int = 2) -> None:
        entries.append(ReportTOCEntry(title=title, anchor=_slugify(title), level=level))

    add(payload.preparation.heading)
    add(payload.shopping_list.heading)
    add(payload.step_by_step.heading)
    add(payload.quality_safety.heading)
    add(payload.time_cost.heading)

    if _has_content(payload.options_upgrades):
        add(payload.options_upgrades.heading)
    if _has_content(payload.maintenance):
        add(payload.maintenance.heading)

    add("FAQ")
    add("Als Nächstes")
    return entries


def _has_content(section: Optional[NarrativeSection]) -> bool:
    if not section:
        return False
    return bool(section.paragraphs or section.bullets or section.note)


def _ensure_meta(payload: ReportPayload) -> ReportMeta:
    meta = payload.meta.model_copy()
    if not meta.difficulty:
        meta.difficulty = "Mittel"

    duration, budget = _derive_meta_from_time_cost(payload.time_cost)
    if duration and _is_unknown(meta.duration):
        meta.duration = duration
    if budget and _is_unknown(meta.budget):
        meta.budget = budget
    if meta.region:
        meta.region = meta.region.strip()
    return meta


def _derive_meta_from_time_cost(section: TimeCostSection) -> tuple[Optional[str], Optional[str]]:
    if not section.rows:
        return (None, None)

    duration_min = 0.0
    duration_max = 0.0
    cost_min = 0.0
    cost_max = 0.0
    has_duration = False
    has_cost = False

    for row in section.rows:
        d_min, d_max = _parse_duration_cell(row.duration)
        if d_min is not None:
            has_duration = True
            duration_min += d_min
            duration_max += d_max if d_max is not None else d_min

        if row.buffer:
            p_d_min, p_d_max = _parse_duration_cell(row.buffer)
            if p_d_min is not None:
                has_duration = True
                duration_min += p_d_min
                duration_max += p_d_max if p_d_max is not None else p_d_min

        c_min, c_max = _parse_cost_cell(row.cost)
        if c_min is not None:
            has_cost = True
            cost_min += c_min
            cost_max += c_max if c_max is not None else c_min

        if row.buffer:
            p_c_min, p_c_max = _parse_cost_cell(row.buffer)
            if p_c_min is not None:
                has_cost = True
                cost_min += p_c_min
                cost_max += p_c_max if p_c_max is not None else p_c_min

    duration_text = _format_duration_range(duration_min, duration_max) if has_duration else None
    cost_text = _format_currency_range(cost_min, cost_max) if has_cost else None
    return (duration_text, cost_text)


def _is_unknown(value: str) -> bool:
    return not value or value.strip().lower() in {"k.a.", "n/a", "unbekannt"}


def _render_markdown(payload: ReportPayload) -> str:
    template: Template = _JINJA_ENV.get_template(_REPORT_TEMPLATE_NAME)
    rendered = template.render(payload=payload)
    return rendered.strip() + "\n"


def _compose_messages_diy(payload: str, original_query: str, product_results: List[dict]) -> List[dict[str, str]]:
    product_hint = (
        "Nutze die gelieferten 'product_results'. Jeder Eintrag besitzt ein Feld 'id'. Die Einkaufsliste muss jeden gelieferten Bauhaus-Artikel (gleiche Reihenfolge wie ids) abbilden."
        if product_results
        else "Wenn keine Produkte vorliegen, setze in shopping_list.items eine leere Liste und verwende shopping_list.empty_hint."
    )

    system_prompt_template = (
        "Du bist ein Heimwerker-Coach. Erstelle für \"{query}\" einen strukturierten Premium-Report als JSON. "
        "Halte dich exakt an das Schema: \n"
        "{{\n"
        "  \"short_summary\": string,\n"
        "  \"report_payload\": {{\n"
        "    \"title\": string,\n"
        "    \"teaser\": string,\n"
        "    \"meta\": {{\"difficulty\": string, \"duration\": string, \"budget\": string, \"region\": string|null}},\n"
        "    \"preparation\": {{\"heading\": string, \"paragraphs\": [string], \"bullets\": [string], \"note\": string|null}},\n"
        "    \"shopping_list\": {{\"heading\": string, \"intro\": string|null, \"items\": [ShoppingItem], \"empty_hint\": string}},\n"
        "    \"step_by_step\": {{\"heading\": string, \"steps\": [StepDetail]}},\n"
        "    \"quality_safety\": NarrativeSection,\n"
        "    \"time_cost\": {{\"heading\": string, \"rows\": [TimeCostRow], \"summary\": string|null}},\n"
        "    \"options_upgrades\": NarrativeSection|null,\n"
        "    \"maintenance\": NarrativeSection|null,\n"
        "    \"faq\": [{{\"question\": string, \"answer\": string}}],\n"
        "    \"followups\": [string]\n"
        "  }},\n"
        "  \"followup_questions\": [string]\n"
        "}}\n"
        "Definitions: NarrativeSection = {heading, paragraphs, bullets, note}; StepDetail = {title, bullets, check, tip|null, warning|null}; TimeCostRow = {work_package, duration, cost, buffer|null}; ShoppingItem = {category, product, quantity, rationale, price|null, url|null}. "
        "Berücksichtige: {product_hint}\n"
        "Regeln: Schwierigkeitsgrad (Anfänger/Fortgeschritten/Profi), Dauer und Budget als realistische Spannen inkl. Puffer. Einkaufsliste mindestens sechs unterschiedliche Positionen (Material, Werkzeuge, Zubehör, Sicherheit, Verbrauchsmaterial) – mehr sind erlaubt, Duplikate vermeiden. Schritt-für-Schritt mindestens 8 Schritte mit Prüfkriterium. FAQ genau 5 Einträge. Followups 4–6 handlungsorientierte Punkte, beginnend mit 'Als Nächstes'. Keine Markdown-Syntax in den Strings selbst."
    )

    system_prompt = (
        system_prompt_template
        .replace("{query}", original_query)
        .replace("{product_hint}", product_hint)
    )

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Hier sind Anfrage und Recherchezusammenfassungen als JSON:\n{payload}"},
    ]


def _compose_messages_ki_control(payload: str) -> List[dict[str, str]]:
    system_prompt = (
        "Du bist ein KI-Governance-Analyst. Erstelle einen strukturierten Markdown-Report zur Steuerung und Evaluierung von KI-Agenten im Heimwerker-Kontext. "
        "Pflichtabschnitte: 1) Ziel & Kontext, 2) Steuerbare Aspekte (Tools, Prompts, Guardrails), 3) Risiken & Mitigations, 4) Metriken (Halluzination, Coverage, Freshness), "
        "5) Evaluationsplan (Testfaelle, Akzeptanzkriterien), 6) Governance (Freigaben, Logging, Tracing), 7) Empfehlungen & Roadmap, 8) FAQ. "
        "Nutze sachliches Deutsch, klare Listen, Tabellen und Hervorhebungen. Antworte ausschließlich mit JSON (short_summary, markdown_report, followup_questions mit 4-6 Fragen)."
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Hier sind Anfrage und Zusammenfassungen als JSON:\n{payload}"},
    ]


async def _invoke_writer_model(
    messages: List[dict[str, str]],
    settings: ModelSettings,
    schema: Optional[Dict[str, Any]] = None,
) -> str:
    client = _get_client()
    kwargs = settings.to_openai_kwargs()

    chat_kwargs: Dict[str, Any] = {
        "model": kwargs.get("model", settings.model),
        "messages": messages,
        "temperature": kwargs.get("temperature", 0.2),
    }

    if schema is not None:
        chat_kwargs["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": "PremiumReport",
                "schema": schema,
            },
        }
    else:
        chat_kwargs["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": "ReportData",
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
        }

    if kwargs.get("max_tokens") is not None:
        chat_kwargs["max_tokens"] = kwargs["max_tokens"]

    response = await traced_completion(
        "writer",
        settings.model,
        {"messages": messages},
        lambda: client.chat.completions.create(**chat_kwargs),
    )
    return extract_output_text(response).strip()


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


def _parse_duration_cell(text: str) -> tuple[Optional[float], Optional[float]]:
    duration_pattern = re.compile(
        r"(?P<min>\d+(?:[.,]\d+)?)\s*(?:[-–]\s*(?P<max>\d+(?:[.,]\d+)?))?\s*(?P<unit>stunden?|std|h|tage?|tag|t)",
        re.IGNORECASE,
    )
    match = duration_pattern.search(text or "")
    if not match:
        return (None, None)

    min_value = _normalize_number(match.group("min"))
    max_group = match.group("max")
    max_value = _normalize_number(max_group) if max_group else None
    unit = (match.group("unit") or "h").lower()

    multiplier = 1.0
    if unit.startswith("tag") or unit == "t":
        multiplier = 8.0

    min_hours = float(min_value) * multiplier
    max_hours = float(max_value) * multiplier if max_value is not None else None
    return (min_hours, max_hours)


def _parse_cost_cell(text: str) -> tuple[Optional[float], Optional[float]]:
    cost_pattern = re.compile(
        r"(?P<min>\d{1,3}(?:[.\s]\d{3})*(?:[.,]\d{1,2})?)\s*(?:[-–]\s*(?P<max>\d{1,3}(?:[.\s]\d{3})*(?:[.,]\d{1,2})?))?\s*€",
        re.IGNORECASE,
    )
    match = cost_pattern.search(text or "")
    if not match:
        return (None, None)

    min_value = _normalize_number(match.group("min"))
    max_group = match.group("max")
    max_value = _normalize_number(max_group) if max_group else None
    return (float(min_value), float(max_value) if max_value is not None else None)


def _normalize_number(value: Optional[str]) -> float:
    if value is None:
        return 0.0
    normalized = value.replace(" ", "").replace(".", "").replace(",", ".")
    try:
        return float(normalized)
    except ValueError:
        return 0.0


def _format_duration_range(min_hours: float, max_hours: float) -> str:
    if max_hours is None or max_hours <= 0:
        max_hours = min_hours
    if min_hours == 0 and max_hours == 0:
        return "k.A."
    if abs(max_hours - min_hours) < 0.25:
        return f"ca. {_format_decimal(min_hours)} h"
    if max_hours >= 16:
        min_days = min_hours / 8.0
        max_days = max_hours / 8.0
        if abs(max_days - min_days) < 0.25:
            return f"ca. {_format_decimal(min_days)} Tage"
        return f"{_format_decimal(min_days)}–{_format_decimal(max_days)} Tage"
    return f"{_format_decimal(min_hours)}–{_format_decimal(max_hours)} h"


def _format_currency_range(min_eur: float, max_eur: float) -> str:
    if max_eur is None or max_eur <= 0:
        max_eur = min_eur
    if min_eur == 0 and max_eur == 0:
        return "k.A."
    if abs(max_eur - min_eur) < 0.5:
        return f"ca. {_format_currency(max_eur)} €"
    return f"{_format_currency(min_eur)}–{_format_currency(max_eur)} €"


def _format_decimal(value: float) -> str:
    rounded = round(value, 1)
    if abs(rounded - round(rounded)) < 0.05:
        return str(int(round(rounded)))
    return f"{rounded:.1f}".replace(".", ",")


def _format_currency(value: float) -> str:
    rounded = round(value)
    return f"{rounded:,.0f}".replace(",", ".")


def _slugify(text: str) -> str:
    normalized = (
        text.replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("Ä", "ae")
        .replace("Ö", "oe")
        .replace("Ü", "ue")
        .replace("ß", "ss")
    )
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", normalized.lower()).strip("-")
    return slug or "section"


