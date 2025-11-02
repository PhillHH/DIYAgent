"""E-Mail-Agent zum Versand der DIY-Berichte via SendGrid.

Das Modul wandelt den Markdown-Report in minimalistisches HTML um und sendet
ihn ueber den SendGrid-Endpunkt. Vor dem Versand werden Guardrails und Felder
validiert."""

from __future__ import annotations

import html
import logging
import re
from typing import List, Optional, Sequence

import httpx
from markdown import markdown as md_to_html

from agents.schemas import ReportData
from models.types import ProductItem
from config import FROM_EMAIL, SENDGRID_API_KEY
from util.url_sanitizer import clean_product_url

MAX_EMAIL_SIZE = 500_000  # Zeichenbegrenzung fuer HTML-Inhalt
EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
SENDGRID_API_URL = "https://api.sendgrid.com/v3/mail/send"
_LOGGER = logging.getLogger(__name__)

DEFAULT_BRAND = {
    "name": "DIY Research Agent",
    "logo": "https://example.com/logo.png",
    "primary": "#1a7f72",
    "secondary": "#ecfdf5",
    "font_stack": '"Inter", "Segoe UI", Arial, sans-serif',
    "cta_url": "https://diyresearch.agent/app",
}

DEFAULT_META = {
    "level": "Anfänger",
    "duration": "14–18 h",
    "budget": "250–450 €",
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

    html_content = _render_html(
        report,
        product_results=product_results,
        brand=brand,
        meta=meta,
    )
    if len(html_content) > MAX_EMAIL_SIZE:
        raise ValueError("Die E-Mail ueberschreitet die zulaessige Groesse")

    _LOGGER.debug("Renderte Premium-E-Mail mit %s Zeichen", len(html_content))

    payload = _build_payload(report, to_email, html_content)
    links = _extract_links(html_content)
    html_preview = html_content[:2000]
    response = await _post_sendgrid(payload)

    return {
        "status": "sent" if 200 <= response.status_code < 300 else "failed",
        "status_code": response.status_code,
        "links": links,
        "html_preview": html_preview,
    }


def _render_html(
    report: ReportData,
    *,
    product_results: Optional[Sequence[ProductItem]] = None,
    brand: Optional[dict] = None,
    meta: Optional[dict] = None,
) -> str:
    """Wandelt Markdown in ein gebrandetes Premium-HTML-Dokument um."""

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

    toc_html = _render_toc(toc_entries)
    product_html = _render_product_list(sanitized_products)
    title = _extract_title(markdown_original)
    subject = _derive_subject(report)
    preheader = _build_preheader(report)
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
    return html_document


def _build_payload(report: ReportData, to_email: str, html_content: str) -> dict:
    """Erstellt den JSON-Payload fuer SendGrid."""

    subject = _derive_subject(report)
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


def _derive_subject(report: ReportData) -> str:
    """Leitet die Betreffzeile aus dem Titel bzw. der Kurzfassung ab."""

    headline = report.short_summary.split(".")[0].strip() or _extract_title(report.markdown_report)
    return f"Premium DIY-Report: {headline}"


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
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    return slug or "section"


def _inject_heading_ids(html_body: str, entries: List[tuple[str, str, int]]) -> str:
    updated = html_body
    for text, slug, level in entries:
        pattern = re.compile(rf"<h{level}(?:\s+[^>]*)?>\s*{re.escape(text)}\s*</h{level}>")
        replacement = f"<h{level} id=\"{slug}\">{html.escape(text)}</h{level}>"
        updated = pattern.sub(replacement, updated, count=1)
    return updated


def _enhance_tables(html_body: str) -> str:
    return re.sub(r"<table>", "<table class=\"table\" role=\"table\">", html_body)


def _enhance_blockquotes(html_body: str) -> str:
    return html_body.replace("<blockquote>", "<blockquote class=\"callout\" role=\"note\">")


def _render_toc(entries: List[tuple[str, str, int]]) -> str:
    if not entries:
        return ""

    items = []
    for text, slug, level in entries:
        css_class = "toc-item" if level == 2 else "toc-subitem"
        items.append(
            f"<li class=\"{css_class}\"><a href=\"#{slug}\" aria-label=\"Springe zu {html.escape(text)}\">{html.escape(text)}</a></li>"
        )

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


def _build_preheader(report: ReportData) -> str:
    summary = (report.short_summary or "").strip()
    if not summary:
        return "Premium DIY-Report – alle Schritte und Materialien auf einen Blick."
    return summary[:180]


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
    brand_name = brand.get("name", "DIY Research Agent")
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
        chips.append(f"<span class=\"meta-chip\">Niveau: {html.escape(meta['level'])}</span>")
    if meta.get("duration"):
        chips.append(f"<span class=\"meta-chip\">Dauer: {html.escape(meta['duration'])}</span>")
    if meta.get("budget"):
        chips.append(f"<span class=\"meta-chip\">Budget: {html.escape(meta['budget'])}</span>")

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
        return ""

    items: List[str] = []
    for product in products:
        price_text = product.price_text.strip() if product.price_text else "ca. Preis auf Anfrage"
        note = (product.note or "").strip()
        note_block = (
            f"<span class=\"product-note\">{html.escape(note)}</span>" if note else ""
        )
        url_str = str(product.url)
        if url_str.startswith("https://www.bauhaus."):
            title_html = (
                f"<a href=\"{html.escape(url_str)}\" rel=\"noopener\" aria-label=\"Produktlink: {html.escape(product.title)}\">"
                f"{html.escape(product.title)}</a>"
            )
        else:
            title_html = f"<span class=\"product-title\">{html.escape(product.title)}</span>"
        items.append(
            "<li class=\"product-item\">"
            f"{title_html}"
            f"<span class=\"product-meta\">{html.escape(price_text)}</span>"
            f"{note_block}"
            "</li>"
        )

    return (
        "<section class=\"section products\" id=\"einkaufsliste\">"
        "<h2>Einkaufsliste Bauhaus</h2>"
        "<ul class=\"product-list\">"
        + "".join(items)
        + "</ul></section>"
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
    brand_name = brand.get("name", "DIY Research Agent")
    return (
        "<section class=\"signature\" id=\"signatur\">"
        "<p>Freundliche Grüße</p>"
        f"<p>{html.escape(brand_name)} · Automatisierter DIY-Service</p>"
        "<p class=\"legal\">Du erhältst diese Nachricht, weil du einen Premium-Report angefordert hast. Bitte prüfe Schutz- und Entsorgungshinweise vor der Umsetzung.</p>"
        "</section>"
    )


def _extract_title(markdown: str) -> str:
    for line in markdown.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return "DIY-Projekt"


def _premium_styles(brand: dict[str, str]) -> str:
    primary = brand.get("primary", "#1a7f72")
    secondary = brand.get("secondary", "#ecfdf5")
    font_stack = brand.get("font_stack", '"Inter", "Segoe UI", Arial, sans-serif')

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


