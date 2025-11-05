"""E-Mail-Agent zum Versand der Home-Task-AI-Projektberichte via SendGrid.

Das Modul wandelt den Markdown-Report in typografisch formatiertes HTML um und sendet
ihn ueber den SendGrid-Endpunkt. Vor dem Versand werden Guardrails und Felder
validiert."""

from __future__ import annotations

import html
import logging
import re
from pathlib import Path
from typing import List, Optional, Sequence

import httpx
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markdown import markdown as md_to_html

from agents.schemas import ReportData
from models.report_payload import (
    NarrativeSection,
    ReportPayload,
    ReportTOCEntry,
    ShoppingItem,
    ShoppingList,
    TimeCostSection,
)
from models.types import ProductItem
from config import FROM_EMAIL, SENDGRID_API_KEY
from util.url_sanitizer import clean_product_url

MAX_EMAIL_SIZE = 500_000  # Zeichenbegrenzung fuer HTML-Inhalt
EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
SENDGRID_API_URL = "https://api.sendgrid.com/v3/mail/send"
_LOGGER = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
_JINJA_ENV = Environment(
    loader=FileSystemLoader(_TEMPLATE_DIR),
    autoescape=select_autoescape(disabled_extensions=("html.j2",)),
    trim_blocks=True,
    lstrip_blocks=True,
)
_EMAIL_TEMPLATE_NAME = "email.html.j2"

DEFAULT_BRAND = {
    "name": "Home Task AI",
    "logo": "https://example.com/logo.png",
    "primary": "#0f766e",
    "secondary": "#f8f4ec",
    "font_stack": '"Rubik", "Inter", "Segoe UI", sans-serif',
    "cta_url": "https://hometask.ai/app",
}

DEFAULT_META = {
    "level": "",
    "duration": "",
    "budget": "",
    "region": "DE",
}

DEFAULT_ATTACHMENT_NOTE = "Anhänge: wird separat generiert"


def ensure_environment() -> None:
    """Stellt sicher, dass die benoetigten SendGrid-Variablen gesetzt sind."""

    if not SENDGRID_API_KEY:
        raise ValueError("SENDGRID_API_KEY ist nicht gesetzt")
    if not FROM_EMAIL:
        raise ValueError("FROM_EMAIL ist nicht gesetzt")


async def send_email(
    report: ReportData,
    to_email: str,
    product_results: Optional[Sequence[ProductItem]] = None,
    brand: Optional[dict] = None,
    meta: Optional[dict] = None,
) -> dict:
    """Sendet den Report per SendGrid und gibt ein Status-Dictionary zurueck.

    Args:
        report: Das bereits validierte `ReportData`-Objekt.
        to_email: Empfaengeradresse.
        product_results: Optionale Produktliste (z. B. aus Bauhaus-Suche).
        brand: Branding-Override (Farben, Logo, CTA).
        meta: Meta-Informationen (Niveau, Dauer, Budget).

    Raises:
        ValueError: Bei leerem Report, ungueltiger Adresse oder Guardrail-Verletzung.
        RuntimeError: Wenn SendGrid mit einem Fehlerstatus antwortet.

    Returns:
        Dictionary mit Versandstatus (`status`, `status_code`) sowie Hilfsinformationen
        (`links`, `html_preview`).
    """

    ensure_environment()

    if not report.markdown_report.strip():
        raise ValueError("Der Report ist leer und kann nicht versendet werden")

    if not EMAIL_REGEX.match(to_email or ""):
        raise ValueError("Die Zieladresse ist ungueltig")

    if report.payload:
        html_content, subject, meta_info = _render_structured_email(
            report,
            report.payload,
            brand=brand,
            meta_override=meta,
        )
    else:
        derived_meta = _extract_meta_from_report(report.markdown_report)
        html_content, subject, meta_info = _render_html_legacy(
            report,
            product_results=product_results,
            brand=brand,
            meta={**(meta or {}), **derived_meta},
        )
    if len(html_content) > MAX_EMAIL_SIZE:
        raise ValueError("Die E-Mail ueberschreitet die zulaessige Groesse")

    _LOGGER.debug("Renderte Premium-E-Mail mit %s Zeichen", len(html_content))
    _LOGGER.info("EMAIL preview length: %s", len(html_content))

    payload = _build_payload(report, to_email, html_content, subject)
    links = _extract_links(html_content)
    html_preview = html_content[:2000]
    response = await _post_sendgrid(payload)

    return {
        "status": "sent" if 200 <= response.status_code < 300 else "failed",
        "status_code": response.status_code,
        "links": links,
        "html_preview": html_preview,
    }


def _render_structured_email(
    report: ReportData,
    payload: ReportPayload,
    *,
    brand: Optional[dict],
    meta_override: Optional[dict],
) -> tuple[str, str, dict[str, str]]:
    brand_data = _merge_brand(brand)
    meta_info = _resolve_meta(meta_override)

    if payload.meta.difficulty:
        meta_info["level"] = payload.meta.difficulty
    if payload.meta.duration:
        meta_info["duration"] = payload.meta.duration
    if payload.meta.budget:
        meta_info["budget"] = payload.meta.budget
    if payload.meta.region:
        meta_info["region"] = payload.meta.region

    working_payload = payload.model_copy(deep=True)
    working_payload.shopping_list = _sanitize_shopping_list_items(working_payload.shopping_list)
    working_payload.toc = _build_structured_toc(working_payload)

    summary_cards_html = _render_summary_cards_structured(report, working_payload, meta_info)
    toc_html = _render_toc_entries(working_payload.toc)
    sections_html = _render_structured_sections(working_payload)

    subject = _derive_subject(working_payload.title, report, meta_info)
    preheader = _build_preheader(report, working_payload.title, meta_info)
    header_html = _render_header(working_payload.title, brand_data, meta_info)
    cta_html = _render_cta(brand_data)
    signature_html = _render_signature(brand_data)
    styles = _premium_styles(brand_data)

    template = _JINJA_ENV.get_template(_EMAIL_TEMPLATE_NAME)
    html_document = template.render(
        subject=subject,
        preheader=preheader,
        styles=styles,
        header_html=header_html,
        toc_html=toc_html,
        summary_cards_html=summary_cards_html,
        sections_html=sections_html,
        cta_html=cta_html,
        attachment_note=DEFAULT_ATTACHMENT_NOTE,
        signature_html=signature_html,
    )

    return html_document, subject, meta_info


def _render_html_legacy(
    report: ReportData,
    *,
    product_results: Optional[Sequence[ProductItem]] = None,
    brand: Optional[dict] = None,
    meta: Optional[dict] = None,
) -> tuple[str, str, dict[str, str]]:
    """Legacy-Markdown-Rendering fuer KI_CONTROL oder Rueckfallpfade."""

    brand_data = _merge_brand(brand)
    meta_info = _resolve_meta(meta)
    sanitized_products = _sanitize_products(product_results)

    markdown_original = report.markdown_report
    toc_entries = _build_toc(markdown_original)
    markdown = _replace_existing_toc(markdown_original, toc_entries)
    html_body = md_to_html(
        markdown,
        extensions=["tables", "fenced_code", "sane_lists"],
    )
    html_body = _inject_heading_ids(html_body, toc_entries)
    html_body = _enhance_tables(html_body)
    html_body = _enhance_blockquotes(html_body)

    meta_from_report = _extract_meta_from_report(markdown_original)
    for key, value in meta_from_report.items():
        if value:
            meta_info[key] = value

    info_blocks = _render_summary_cards(report, meta_info)
    toc_html = _render_toc(toc_entries)
    product_html = _render_product_list(sanitized_products)
    title = _extract_title(markdown_original)
    subject = _derive_subject(title, report, meta_info)
    preheader = _build_preheader(report, title, meta_info)
    header_html = _render_header(title, brand_data, meta_info)
    cta_html = _render_cta(brand_data)
    signature_html = _render_signature(brand_data)

    styles = _premium_styles(brand_data)

    html_document = f"""
    <html>
      <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <style>{styles}</style>
        <title>{html.escape(subject)}</title>
      </head>
      <body>
        <!-- Subject: {html.escape(subject)} -->
        <span class="preheader">{html.escape(preheader)}</span>
        <div class="email-shell">
          <div class="email-container">
            {header_html}
            {toc_html}
            {product_html}
            <div class="content" id="report-content">
              {info_blocks}
              {html_body}
            </div>
            {cta_html}
            <p class="attachment-note">{html.escape(DEFAULT_ATTACHMENT_NOTE)}</p>
            {signature_html}
          </div>
        </div>
      </body>
    </html>
    """
    return html_document, subject, meta_info


def _sanitize_shopping_list_items(shopping: ShoppingList) -> ShoppingList:
    sanitized = shopping.model_copy(deep=True)
    cleaned_items: List[ShoppingItem] = []
    for item in sanitized.items:
        url_value: Optional[str] = None
        if item.url:
            try:
                url_value = clean_product_url(str(item.url))
            except ValueError:
                url_value = str(item.url)
        cleaned_items.append(
            ShoppingItem(
                position=item.position,
                category=item.category,
                product=item.product,
                quantity=item.quantity,
                rationale=item.rationale,
                price=item.price,
                url=url_value,
            )
        )
    deduped: List[ShoppingItem] = []
    seen_categories: set[str] = set()
    for item in cleaned_items:
        category_key = (item.category or "").strip().lower()
        if category_key in seen_categories:
            continue
        seen_categories.add(category_key)
        deduped.append(item)
    sanitized.items = deduped
    return sanitized


def _build_structured_toc(payload: ReportPayload) -> List[ReportTOCEntry]:
    entries: List[ReportTOCEntry] = []

    def add(title: str, level: int = 2) -> None:
        entries.append(ReportTOCEntry(title=title, anchor=_slugify(title), level=level))

    add(payload.preparation.heading)
    add(payload.shopping_list.heading)
    add(payload.step_by_step.heading)
    add(payload.quality_safety.heading)
    add(payload.time_cost.heading)

    if _has_narrative_content(payload.options_upgrades):
        add(payload.options_upgrades.heading)
    if _has_narrative_content(payload.maintenance):
        add(payload.maintenance.heading)

    add("FAQ")
    add("Als Nächstes")
    return entries


def _render_toc_entries(entries: Sequence[ReportTOCEntry]) -> str:
    if not entries:
        return ""

    items: List[str] = []
    last_level = None
    for entry in entries:
        css_class = "toc-item" if entry.level == 2 else "toc-subitem"
        if last_level is not None and entry.level < last_level:
            items.append("<li class=\"toc-divider\"></li>")
        items.append(
            f"<li class=\"{css_class}\"><a href=\"#{html.escape(entry.anchor)}\" aria-label=\"Springe zu {html.escape(entry.title)}\">{html.escape(entry.title)}</a></li>"
        )
        last_level = entry.level

    return (
        "<nav class=\"toc\" aria-label=\"Inhaltsverzeichnis\">"
        "<h2>Inhalt</h2>"
        "<ul>" + "".join(items) + "</ul>"
        "</nav>"
    )


def _render_summary_cards_structured(
    report: ReportData,
    payload: ReportPayload,
    meta: dict[str, str],
) -> str:
    summary_text = html.escape((report.short_summary or payload.teaser).strip())
    teaser_text = html.escape(payload.teaser.strip()) if payload.teaser else ""

    meta_items = [
        ("Schwierigkeitsgrad", meta.get("level", "")),
        ("Zeitaufwand", meta.get("duration", "")),
        ("Kostenrahmen", meta.get("budget", "")),
        ("Region", meta.get("region", "")),
    ]
    meta_html = "".join(
        f"<li><span>{html.escape(label)}:</span> {html.escape(value)}</li>"
        for label, value in meta_items
        if value and value.lower() != "k.a."
    )

    followup_entries: List[str] = []
    for entry in payload.followups:
        text = (entry or "").strip()
        if not text:
            continue
        followup_entries.append(f"<li>{html.escape(text)}</li>")
    followup_html = "".join(followup_entries)

    search_summary = (
        f"<p class=\"search-summary\"><strong>Recherchefokus:</strong> {html.escape(payload.search_summary)}</p>"
        if payload.search_summary
        else ""
    )

    return (
        "<section class=\"intro-cards\">"
        "<div class=\"card summary\">"
        "<h3>Projektüberblick</h3>"
        f"<p>{summary_text}</p>"
        + (f"<p>{teaser_text}</p>" if teaser_text else "")
        + search_summary
        + "</div>"
        "<div class=\"card meta\">"
        "<h3>Kennzahlen</h3>"
        f"<ul>{meta_html}</ul>"
        "</div>"
        + (
            "<div class=\"card followup\"><h3>Nächste Schritte</h3><ul>"
            + followup_html
            + "</ul></div>"
            if followup_html
            else ""
        )
        + "</section>"
    )


def _render_structured_sections(payload: ReportPayload) -> str:
    parts: List[str] = []
    parts.append(_render_narrative_section(payload.preparation))
    parts.append(_render_shopping_list_section(payload.shopping_list))
    parts.append(_render_steps_section(payload.step_by_step))
    parts.append(_render_narrative_section(payload.quality_safety))
    parts.append(_render_time_cost_section(payload.time_cost))

    if _has_narrative_content(payload.options_upgrades):
        parts.append(_render_narrative_section(payload.options_upgrades))
    if _has_narrative_content(payload.maintenance):
        parts.append(_render_narrative_section(payload.maintenance))

    parts.append(_render_faq_section(payload.faq))
    parts.append(_render_followups_section(payload.followups))

    return "".join(parts)


def _render_narrative_section(section: Optional[NarrativeSection]) -> str:
    if section is None:
        return ""
    section_id = _slugify(section.heading)
    html_parts = [
        f"<section class=\"section narrative\" id=\"{html.escape(section_id)}\">",
        f"<a id=\"{html.escape(section_id)}\" name=\"{html.escape(section_id)}\"></a>",
        f"<h2>{html.escape(section.heading)}</h2>",
    ]
    for paragraph in section.paragraphs:
        html_parts.append(f"<p>{html.escape(paragraph)}</p>")
    if section.bullets:
        html_parts.append("<ul class=\"bullet-list\">")
        for bullet in section.bullets:
            html_parts.append(f"<li>{html.escape(bullet)}</li>")
        html_parts.append("</ul>")
    if section.note:
        html_parts.append(f"<blockquote class=\"callout\">{html.escape(section.note)}</blockquote>")
    html_parts.append("</section>")
    return "".join(html_parts)


def _render_shopping_list_section(shopping: ShoppingList) -> str:
    section_id = _slugify(shopping.heading)
    if not shopping.items:
        return (
            f"<section class=\"section products\" id=\"{html.escape(section_id)}\">"
            f"<a id=\"{html.escape(section_id)}\" name=\"{html.escape(section_id)}\"></a>"
            f"<h2>{html.escape(shopping.heading)}</h2>"
            f"<p>{html.escape(shopping.empty_hint)}</p>"
            "</section>"
        )

    header_html = (
        f"<section class=\"section products\" id=\"{html.escape(section_id)}\">"
        f"<a id=\"{html.escape(section_id)}\" name=\"{html.escape(section_id)}\"></a>"
        f"<h2>{html.escape(shopping.heading)}</h2>"
    )
    intro_html = f"<p>{html.escape(shopping.intro)}</p>" if shopping.intro else ""
    table_header = (
        "<table class=\"table product-table\" role=\"table\">"
        "<thead><tr><th>Position</th><th>Kategorie</th><th>Produkt</th><th>Menge</th><th>Begründung</th><th>ca. Preis</th><th>Link</th></tr></thead><tbody>"
    )
    rows: List[str] = []
    for index, item in enumerate(shopping.items, start=1):
        link_cell = "–"
        if item.url:
            link_cell = f"<a href=\"{html.escape(str(item.url))}\" rel=\"noopener\">Zum Artikel</a>"
        rows.append(
            "<tr>"
            f"<td>{index}</td>"
            f"<td>{html.escape(item.category)}</td>"
            f"<td>{html.escape(item.product)}</td>"
            f"<td>{html.escape(item.quantity)}</td>"
            f"<td>{html.escape(item.rationale)}</td>"
            f"<td>{html.escape(item.price or '–')}</td>"
            f"<td>{link_cell}</td>"
            "</tr>"
        )
    table_footer = "</tbody></table></section>"
    return header_html + intro_html + table_header + "".join(rows) + table_footer


def _render_steps_section(steps_section) -> str:
    section_id = _slugify(steps_section.heading)
    parts = [
        f"<section class=\"section steps\" id=\"{html.escape(section_id)}\">",
        f"<a id=\"{html.escape(section_id)}\" name=\"{html.escape(section_id)}\"></a>",
        f"<h2>{html.escape(steps_section.heading)}</h2>",
        "<div class=\"step-grid\">",
    ]
    for index, step in enumerate(steps_section.steps, start=1):
        parts.append("<div class=\"step-card\">")
        parts.append(
            "<header>"
            f"<span class=\"step-index\">{index}</span>"
            f"<h3>Schritt {index}: {html.escape(step.title)}</h3>"
            "</header>"
        )
        if step.bullets:
            parts.append("<ul class=\"bullet-list\">")
            for bullet in step.bullets:
                parts.append(f"<li>{html.escape(bullet)}</li>")
            parts.append("</ul>")
        parts.append(f"<p class=\"step-check\"><strong>Prüfkriterium:</strong> {html.escape(step.check)}</p>")
        if step.tip:
            parts.append(f"<blockquote class=\"callout tip\">{html.escape(step.tip)}</blockquote>")
        if step.warning:
            parts.append(f"<blockquote class=\"callout warning\">{html.escape(step.warning)}</blockquote>")
        parts.append("</div>")
    parts.append("</div></section>")
    return "".join(parts)


def _render_time_cost_section(section: TimeCostSection) -> str:
    section_id = _slugify(section.heading)
    parts = [
        f"<section class=\"section time-cost\" id=\"{html.escape(section_id)}\">",
        f"<a id=\"{html.escape(section_id)}\" name=\"{html.escape(section_id)}\"></a>",
        f"<h2>{html.escape(section.heading)}</h2>",
    ]
    if section.rows:
        parts.append(
            "<table class=\"table time-cost-table\" role=\"table\">"
            "<thead><tr><th>Arbeitspaket</th><th>Dauer</th><th>Kosten</th><th>Puffer</th></tr></thead><tbody>"
        )
        for row in section.rows:
            parts.append(
                "<tr>"
                f"<td>{html.escape(row.work_package)}</td>"
                f"<td>{html.escape(row.duration)}</td>"
                f"<td>{html.escape(row.cost)}</td>"
                f"<td>{html.escape(row.buffer or '–')}</td>"
                "</tr>"
            )
        parts.append("</tbody></table>")
    if section.summary:
        parts.append(f"<p>{html.escape(section.summary)}</p>")
    parts.append("</section>")
    return "".join(parts)


def _render_faq_section(faq_items) -> str:
    parts = [
        f"<section class=\"section faq\" id=\"{html.escape(_slugify('FAQ'))}\">",
        f"<a id=\"{html.escape(_slugify('FAQ'))}\" name=\"{html.escape(_slugify('FAQ'))}\"></a>",
        "<h2>FAQ</h2>",
    ]
    for item in faq_items:
        parts.append(f"<h3>{html.escape(item.question)}</h3>")
        parts.append(f"<p>{html.escape(item.answer)}</p>")
    parts.append("</section>")
    return "".join(parts)


def _render_followups_section(followups: Sequence[str]) -> str:
    section_id = _slugify("Als Nächstes")
    parts = [
        f"<section class=\"section followups\" id=\"{html.escape(section_id)}\">",
        f"<a id=\"{html.escape(section_id)}\" name=\"{html.escape(section_id)}\"></a>",
        "<h2>Als Nächstes</h2>",
        "<ul class=\"bullet-list\">",
    ]
    for entry in followups:
        parts.append(f"<li>{html.escape(entry)}</li>")
    parts.append("</ul></section>")
    return "".join(parts)


def _has_narrative_content(section: Optional[NarrativeSection]) -> bool:
    if not section:
        return False
    return bool(section.paragraphs or section.bullets or section.note)


def _build_payload(report: ReportData, to_email: str, html_content: str, subject: str) -> dict:
    """Erstellt den JSON-Payload fuer SendGrid."""

    return {
        "personalizations": [
            {
                "to": [{"email": to_email}],
            }
        ],
        "from": {"email": FROM_EMAIL},
        "subject": subject,
        "content": [
            {
                "type": "text/html",
                "value": html_content,
            }
        ],
    }


def _derive_subject(title: str, report: ReportData, meta: dict[str, str]) -> str:
    """Leitet die Betreffzeile aus Titel und Meta-Informationen ab."""

    base = title.strip() if title else ""
    if not base:
        base = (report.short_summary.split(".")[0] if report.short_summary else "").strip()
    if not base:
        base = "Home Task AI Projektplan"

    duration = (meta.get("duration") or "").strip()
    budget = (meta.get("budget") or "").strip()

    def _is_known(value: str) -> bool:
        return bool(value) and value.lower() != "k.a."

    if _is_known(duration) and _is_known(budget):
        return f"{base} – in {duration}, ca. {budget}"
    if _is_known(duration):
        return f"{base} – in {duration}"
    if _is_known(budget):
        return f"{base} – ca. {budget}"
    return f"{base} – dein DIY-Plan"


def _build_toc(markdown: str) -> List[tuple[str, str, int]]:
    entries: List[tuple[str, str, int]] = []
    slug_counts: dict[str, int] = {}
    for line in markdown.splitlines():
        if line.startswith("### "):
            level = 3
            text = line[4:].strip()
        elif line.startswith("## "):
            level = 2
            text = line[3:].strip()
        else:
            continue

        if not text:
            continue

        base_slug = _slugify(text)
        count = slug_counts.get(base_slug, 0)
        slug_counts[base_slug] = count + 1
        slug = base_slug if count == 0 else f"{base_slug}-{count}"
        entries.append((text, slug, level))
    return entries


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


def _inject_heading_ids(html_body: str, entries: List[tuple[str, str, int]]) -> str:
    updated = html_body
    for text, slug, level in entries:
        pattern = re.compile(rf"<h{level}(?:\s+[^>]*)?>\s*{re.escape(text)}\s*</h{level}>")
        replacement = (
            f"<a id=\"{slug}\" name=\"{slug}\"></a>"
            f"<h{level} id=\"{slug}\" name=\"{slug}\">{html.escape(text)}</h{level}>"
        )
        updated = pattern.sub(replacement, updated, count=1)
    return updated


def _enhance_tables(html_body: str) -> str:
    return re.sub(r"<table>", "<table class=\"table\" role=\"table\">", html_body)


def _enhance_blockquotes(html_body: str) -> str:
    return html_body.replace("<blockquote>", "<blockquote class=\"callout\" role=\"note\">")


def _render_toc(entries: List[tuple[str, str, int]]) -> str:
    relevant_entries = [(text, slug, level) for text, slug, level in entries if level in {2, 3}]
    if not relevant_entries:
        return ""

    items: List[str] = []
    last_level = None
    for text, slug, level in relevant_entries:
        css_class = "toc-item" if level == 2 else "toc-subitem"
        if last_level is not None and level < last_level:
            items.append("<li class=\"toc-divider\"></li>")
        items.append(
            f"<li class=\"{css_class}\"><a href=\"#{slug}\" aria-label=\"Springe zu {html.escape(text)}\">{html.escape(text)}</a></li>"
        )
        last_level = level

    return (
        "<nav class=\"toc\" aria-label=\"Inhaltsverzeichnis\">"
        "<h2>Inhalt</h2>"
        "<ul>" + "".join(items) + "</ul>"
        "</nav>"
    )


def _merge_brand(brand: Optional[dict]) -> dict[str, str]:
    data = dict(DEFAULT_BRAND)
    if brand:
        for key, value in brand.items():
            if value is not None:
                data[key] = str(value)
    return data


def _resolve_meta(meta: Optional[dict]) -> dict[str, str]:
    data = dict(DEFAULT_META)
    if meta:
        for key, value in meta.items():
            if value is not None:
                data[key] = str(value)
    return data


def _build_preheader(report: ReportData, title: str, meta: dict[str, str]) -> str:
    duration = (meta.get("duration") or "").strip()
    budget = (meta.get("budget") or "").strip()

    def _is_known(value: str) -> bool:
        return bool(value) and value.lower() != "k.a."

    if title and _is_known(duration) and _is_known(budget):
        return f"{title} – in {duration}, ca. {budget}"[:180]

    summary = (report.short_summary or "").strip()
    if summary:
        return summary[:180]

    info_parts: List[str] = []
    if _is_known(duration):
        info_parts.append(f"in {duration}")
    if _is_known(budget):
        info_parts.append(f"ca. {budget}")
    if info_parts:
        return f"Premium DIY-Report – {' und '.join(info_parts)}"[:180]

    return "Premium DIY-Report – alle Schritte und Materialien auf einen Blick."


def _replace_existing_toc(
    markdown: str, entries: List[tuple[str, str, int]]
) -> str:
    pattern = re.compile(
        r"(^##\s+(?:inhaltsverzeichnis|inhalt)[\s\S]*?)(?=\n##\s+|\Z)",
        re.IGNORECASE | re.MULTILINE,
    )
    match = pattern.search(markdown)
    if not match:
        return markdown

    bullet_lines = [f"- [{text}](#{slug})" for text, slug, level in entries if level == 2 or level == 3]
    toc_body = "\n".join(bullet_lines) if bullet_lines else "- [Vorbereitung](#vorbereitung)"
    sanitized = "## Inhaltsverzeichnis\n\n" + toc_body + "\n\n"
    return pattern.sub(sanitized, markdown)


def _render_header(title: str, brand: dict[str, str], meta: dict[str, str]) -> str:
    brand_name = brand.get("name", "Home Task AI")
    logo_url = brand.get("logo")

    if logo_url:
        logo_html = (
            f"<span class=\"brand-logo brand-logo-image\"><img src=\"{html.escape(logo_url)}\" alt=\"{html.escape(brand_name)} Logo\" width=\"54\" height=\"54\" /></span>"
        )
    else:
        initials = "".join(word[0].upper() for word in brand_name.split()[:2]) or "DIY"
        logo_html = f"<span class=\"brand-logo\">{html.escape(initials)}</span>"

    chips = []
    if meta.get("level"):
        chips.append(f"<span class=\"meta-chip\">Schwierigkeitsgrad: {html.escape(meta['level'])}</span>")
    if meta.get("duration"):
        chips.append(f"<span class=\"meta-chip\">Zeitaufwand: {html.escape(meta['duration'])}</span>")
    if meta.get("budget"):
        chips.append(f"<span class=\"meta-chip\">Kostenrahmen: {html.escape(meta['budget'])}</span>")

    chips_html = "".join(chips)

    return (
        "<header class=\"brand-header\">"
        f"{logo_html}"
        "<div class=\"brand-info\">"
        f"<p class=\"brand-name\">{html.escape(brand_name)}</p>"
        f"<h1>{html.escape(title)}</h1>"
        "</div>"
        "</header>"
        f"<div class=\"meta-row\">{chips_html}</div>"
    )


def _sanitize_products(products: Optional[Sequence[ProductItem]]) -> List[ProductItem]:
    if not products:
        return []

    sanitized: List[ProductItem] = []
    seen: set[str] = set()
    for product in products:
        if product is None:
            continue
        try:
            cleaned_url = clean_product_url(str(product.url))
        except ValueError:
            continue

        key = cleaned_url.lower()
        if key in seen:
            continue
        seen.add(key)

        product_dict = product.model_dump()
        product_dict["url"] = cleaned_url
        sanitized.append(ProductItem.model_validate(product_dict))
    return sanitized[:10]


def _render_product_list(products: Sequence[ProductItem]) -> str:
    if not products:
        return (
            "<section class=\"section products\" id=\"einkaufsliste\">"
            "<h2>Einkaufsliste Bauhaus</h2>"
            "<p>Keine geprüften Bauhaus-Produkte verfügbar.</p>"
            "</section>"
        )

    items: List[str] = []
    for product in products:
        price_text = product.price_text.strip() if product.price_text else "ca. Preis auf Anfrage"
        note = (product.note or "").strip()
        note_block = (
            f"<span class=\"product-note\">{html.escape(note)}</span>" if note else ""
        )
        try:
            cleaned_url = clean_product_url(str(product.url))
        except ValueError as exc:
            _LOGGER.info("E-Mail Produktlink verworfen (URL): %s (%s)", product.url, exc)
            continue

        items.append(
            "<li class=\"product-item\">"
            f"<a href=\"{html.escape(cleaned_url)}\" rel=\"noopener\" aria-label=\"Produktlink: {html.escape(product.title)}\">{html.escape(product.title)}</a>"
            f"<span class=\"product-meta\">{html.escape(price_text)}</span>"
            f"{note_block}"
            "</li>"
        )

    if not items:
        return ""

    return (
        "<section class=\"section products\" id=\"einkaufsliste\">"
        "<h2>Einkaufsliste Bauhaus</h2>"
        "<ul class=\"product-list\">"
        + "".join(items)
        + "</ul></section>"
    )


def _render_summary_cards(report: ReportData, meta: dict[str, str]) -> str:
    """Erzeugt Einleitungen mit Projekt-Short-Summary und Metadaten."""

    summary = html.escape(report.short_summary.strip())
    followups = report.followup_questions[:]
    meta_items = [
        ("Schwierigkeitsgrad", meta.get("level", "")),
        ("Zeitaufwand", meta.get("duration", "")),
        ("Kostenrahmen", meta.get("budget", "")),
        ("Region", meta.get("region", "")),
    ]
    meta_html = "".join(
        f"<li><span>{html.escape(label)}:</span> {html.escape(value)}</li>"
        for label, value in meta_items if value and value.lower() != "k.a."
    )

    followup_entries: List[str] = []
    for question in followups[:6]:
        text = (question or "").strip()
        if not text:
            continue
        if not text.lower().startswith("als nächstes"):
            text = f"Als Nächstes: {text}"
        followup_entries.append(f"<li>{html.escape(text)}</li>")
    followup_html = "".join(followup_entries)

    return (
        "<section class=\"intro-cards\">"
        "<div class=\"card summary\">"
        "<h3>Projektüberblick</h3>"
        f"<p>{summary}</p>"
        "</div>"
        "<div class=\"card meta\">"
        "<h3>Kennzahlen</h3>"
        f"<ul>{meta_html}</ul>"
        "</div>"
        + (
            "<div class=\"card followup\"><h3>Nächste Schritte</h3><ul>"
            + followup_html
            + "</ul></div>"
            if followup_html
            else ""
        )
        + "</section>"
    )


def _render_cta(brand: dict[str, str]) -> str:
    cta_url = brand.get("cta_url") or "#"
    safe_url = html.escape(cta_url)
    return (
        "<section class=\"cta\" id=\"abschluss-und-cta\">"
        "<h2>Abschluss &amp; CTA</h2>"
        "<p>Projektkonfiguration geprüft? Öffne die Plattform, um den Versand als PDF oder weitere Korrekturen vorzunehmen.</p>"
        f"<a href=\"{safe_url}\" class=\"button-primary\" aria-label=\"Projekt im Dashboard öffnen\">Projekt im Dashboard öffnen</a>"
        "</section>"
    )


def _render_signature(brand: dict[str, str]) -> str:
    brand_name = brand.get("name", "Home Task AI")
    return (
        "<section class=\"signature\" id=\"signatur\">"
        "<p>Freundliche Grüße</p>"
        f"<p>{html.escape(brand_name)} · Automatisierter Heimwerker-Service</p>"
        "<p class=\"legal\">Du erhältst diese Nachricht, weil du einen Premium-Report angefordert hast. Bitte prüfe Schutz- und Entsorgungshinweise vor der Umsetzung.</p>"
        "</section>"
    )


def _extract_meta_from_report(markdown: str) -> dict[str, str]:
    match = re.search(r"^>\s.*$", markdown, re.MULTILINE)
    if not match:
        return {}
    return _parse_meta_line(match.group(0))


def _parse_meta_line(meta_line: str) -> dict[str, str]:
    cleaned = meta_line.replace("**", "").lstrip("> ")
    parts = [segment.strip() for segment in re.split(r"[·|]", cleaned)]
    result: dict[str, str] = {}
    for part in parts:
        if not part:
            continue
        if ":" in part:
            label, value = part.split(":", 1)
        elif " " in part:
            label, value = part.split(" ", 1)
        else:
            continue
        label = label.strip().lower()
        value = value.strip()
        if not value:
            continue
        if label == "meta" and " " in value:
            nested_label, nested_value = value.split(" ", 1)
            label = nested_label.strip().lower()
            value = nested_value.strip()
            if not value:
                continue
        if label in {"schwierigkeitsgrad", "niveau"}:
            result["level"] = value
        elif label in {"zeitaufwand", "zeit"}:
            result["duration"] = value
        elif label in {"kostenrahmen", "budget"}:
            result["budget"] = value
        elif label == "region":
            result["region"] = value
    return result


def _extract_title(markdown: str) -> str:
    for line in markdown.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return "Heimwerker-Projekt"


def _premium_styles(brand: dict[str, str]) -> str:
    primary = brand.get("primary", "#0f766e")
    secondary = brand.get("secondary", "#f8f4ec")
    font_stack = brand.get("font_stack", '"Rubik", "Inter", "Segoe UI", sans-serif')

    return f"""
    :root {{
      color-scheme: light dark;
    }}
    body {{
      margin: 0;
      padding: 24px 16px;
      font-family: {font_stack};
      background: radial-gradient(160% 160% at 50% 0%, {secondary} 0%, #f8fafc 55%, #f1f5f9 100%);
      color: #1f2937;
    }}
    body.dark, @media (prefers-color-scheme: dark) {{
      body {{
        background: radial-gradient(140% 140% at 50% 0%, rgba(17, 94, 89, 0.45) 0%, #0f172a 80%);
        color: #e2e8f0;
      }}
    }}
    .email-shell {{
      max-width: 760px;
      margin: 0 auto;
    }}
    .email-container {{
      max-width: 720px;
      margin: 0 auto;
      background: rgba(255, 255, 255, 0.96);
      border-radius: 24px;
      padding: 36px 32px;
      box-shadow: 0 25px 70px rgba(15, 23, 42, 0.14);
      line-height: 1.65;
      backdrop-filter: blur(16px);
    }}
    @media (prefers-color-scheme: dark) {{
      .email-container {{
        background: rgba(15, 23, 42, 0.88);
        box-shadow: 0 25px 60px rgba(3, 7, 18, 0.6);
      }}
      .meta-chip {{
        background: rgba(241, 245, 249, 0.1);
        color: #e2e8f0;
      }}
      .toc {{
        background: rgba(15, 118, 110, 0.18);
      }}
    }}
    .brand-header {{
      display: flex;
      align-items: center;
      gap: 18px;
      margin-bottom: 28px;
    }}
    .brand-logo {{
      width: 54px;
      height: 54px;
      border-radius: 14px;
      background: linear-gradient(135deg, {primary}, rgba(26, 127, 114, 0.7));
      display: flex;
      align-items: center;
      justify-content: center;
      color: #f8fafc;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}
    .brand-logo.brand-logo-image {{
      background: none;
      padding: 0;
    }}
    .brand-logo-image img {{
      display: block;
      width: 54px;
      height: 54px;
      border-radius: 14px;
    }}
    .brand-info h1 {{
      margin: 0;
      font-size: 2.1rem;
      color: #0f172a;
    }}
    @media (prefers-color-scheme: dark) {{
      .brand-info h1 {{ color: #f1f5f9; }}
    }}
    .brand-info p {{
      margin: 4px 0 0;
      color: #475569;
    }}
    .meta-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 18px;
    }}
    .meta-chip {{
      padding: 6px 14px;
      border-radius: 999px;
      background: rgba(26, 127, 114, 0.12);
      color: #0f766e;
      font-size: 0.92rem;
      font-weight: 600;
    }}
    .toc {{
      margin: 28px 0;
      padding: 18px 20px;
      background: rgba(26, 127, 114, 0.12);
      border-radius: 18px;
    }}
    .toc h2 {{
      margin: 0 0 10px;
    }}
    .toc ul {{
      list-style: none;
      margin: 0;
      padding-left: 0;
      display: grid;
      gap: 6px;
    }}
    .toc li {{
      font-size: 0.95rem;
    }}
    .toc a {{
      color: {primary};
      text-decoration: none;
    }}
    .toc a:hover {{
      text-decoration: underline;
    }}
    .product-list {{
      list-style: none;
      padding-left: 0;
      margin: 0;
      display: grid;
      gap: 14px;
    }}
    .product-item {{
      padding: 14px 16px;
      border-radius: 16px;
      background: rgba(148, 163, 184, 0.12);
    }}
    .product-item a {{
      font-weight: 600;
      color: {primary};
      text-decoration: none;
    }}
    .product-item a:hover {{
      text-decoration: underline;
    }}
    .product-meta {{
      display: block;
      margin-top: 6px;
      color: #475569;
      font-size: 0.92rem;
    }}
    .product-note {{
      display: block;
      margin-top: 4px;
      color: #64748b;
      font-size: 0.9rem;
    }}
    .content h2 {{
      margin-top: 2.2rem;
      font-size: 1.65rem;
      border-bottom: 2px solid rgba(15, 118, 110, 0.25);
      padding-bottom: 0.35rem;
    }}
    .content h3 {{
      margin-top: 1.6rem;
      font-size: 1.25rem;
    }}
    .content p {{
      margin: 0.7rem 0;
    }}
    .callout {{
      border-left: 4px solid {primary};
      background: rgba(26, 127, 114, 0.1);
      border-radius: 12px;
      padding: 14px 18px;
      margin: 1.4rem 0;
    }}
    .callout.tip {{
      border-left-color: {primary};
    }}
    .callout.warning {{
      border-left-color: #f97316;
      background: rgba(249, 115, 22, 0.12);
    }}
    .bullet-list {{
      margin: 0.6rem 0 0.6rem 1.2rem;
      padding: 0;
    }}
    .bullet-list li {{
      margin-bottom: 0.35rem;
    }}
    .step-grid {{
      display: grid;
      gap: 18px;
      margin: 1.2rem 0;
    }}
    .step-card {{
      border-radius: 18px;
      padding: 18px 20px;
      background: rgba(148, 163, 184, 0.12);
      display: grid;
      gap: 10px;
    }}
    .step-card header {{
      display: flex;
      align-items: center;
      gap: 12px;
    }}
    .step-index {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 36px;
      height: 36px;
      border-radius: 50%;
      background: {primary};
      color: #ffffff;
      font-weight: 600;
      font-size: 1rem;
    }}
    .step-card h3 {{
      margin: 0;
      font-size: 1.1rem;
    }}
    .step-check {{
      margin: 0.4rem 0;
      color: #1f2937;
    }}
    .search-summary {{
      margin-top: 0.8rem;
      color: #475569;
      font-size: 0.95rem;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin: 1.6rem 0;
      overflow: hidden;
      border-radius: 14px;
    }}
    table thead {{
      background: rgba(26, 127, 114, 0.16);
    }}
    table th, table td {{
      padding: 12px 14px;
      border: 1px solid rgba(148, 163, 184, 0.35);
      text-align: left;
      font-size: 0.97rem;
    }}
    table tbody tr:nth-child(even) {{
      background: rgba(15, 118, 110, 0.08);
    }}
    .button-primary {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      padding: 14px 26px;
      border-radius: 999px;
      background: linear-gradient(135deg, {primary}, rgba(26, 127, 114, 0.82));
      color: #f8fafc;
      text-decoration: none;
      font-weight: 600;
      box-shadow: 0 12px 30px rgba(15, 118, 110, 0.22);
    }}
    .button-primary:hover {{
      filter: brightness(1.05);
    }}
    .cta {{
      margin-top: 32px;
      text-align: center;
    }}
    .cta p {{
      color: #475569;
    }}
    @media (prefers-color-scheme: dark) {{
      .cta p {{ color: #cbd5f5; }}
      .product-meta, .product-note {{ color: #cbd5f5; }}
      .search-summary {{ color: #cbd5f5; }}
      .step-card {{ background: rgba(148, 163, 184, 0.18); }}
      .step-check {{ color: #e2e8f0; }}
    }}
    .signature {{
      margin-top: 38px;
      font-size: 0.92rem;
      color: #475569;
    }}
    @media (prefers-color-scheme: dark) {{
      .signature {{ color: #cbd5f5; }}
    }}
    .preheader {{
      display: none !important;
      visibility: hidden;
      opacity: 0;
      height: 0;
      width: 0;
      overflow: hidden;
      mso-hide: all;
    }}
    .attachment-note {{
      margin-top: 26px;
      font-size: 0.85rem;
      color: #64748b;
      text-align: center;
    }}
    """


def _extract_links(html_content: str) -> List[str]:
    return re.findall(r'href="([^"#]+(?:#[^"]*)?)"', html_content)


async def _post_sendgrid(payload: dict) -> httpx.Response:
    """Sendet die Anfrage asynchron an die SendGrid-API."""

    headers = {
        "Authorization": f"Bearer {SENDGRID_API_KEY}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(SENDGRID_API_URL, json=payload, headers=headers)

    if response.status_code >= 300:
        raise RuntimeError(
            f"SendGrid antwortete mit {response.status_code}: {response.text.strip()}"
        )

    return response


