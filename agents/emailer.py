"""E-Mail-Agent zum Versand der DIY-Berichte via SendGrid.

Das Modul wandelt den Markdown-Report in minimalistisches HTML um und sendet
ihn ueber den SendGrid-Endpunkt. Vor dem Versand werden Guardrails und Felder
validiert."""

from __future__ import annotations

import asyncio
import html
import logging
import re
from typing import List

import httpx
from markdown import markdown as md_to_html

from agents.schemas import ReportData
from config import FROM_EMAIL, SENDGRID_API_KEY
from guards.output_guard import validate_report

MAX_EMAIL_SIZE = 500_000  # Zeichenbegrenzung fuer HTML-Inhalt
EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
SENDGRID_API_URL = "https://api.sendgrid.com/v3/mail/send"
_LOGGER = logging.getLogger(__name__)


def ensure_environment() -> None:
    """Stellt sicher, dass die benoetigten SendGrid-Variablen gesetzt sind."""

    if not SENDGRID_API_KEY:
        raise ValueError("SENDGRID_API_KEY ist nicht gesetzt")
    if not FROM_EMAIL:
        raise ValueError("FROM_EMAIL ist nicht gesetzt")


async def send_email(report: ReportData, to_email: str) -> dict:
    """Sendet den Report per SendGrid und gibt ein Status-Dictionary zurueck.

    Args:
        report: Das bereits validierte `ReportData`-Objekt.
        to_email: Empfaengeradresse.

    Raises:
        ValueError: Bei leerem Report, ungueltiger Adresse oder Guardrail-Verletzung.
        RuntimeError: Wenn SendGrid mit einem Fehlerstatus antwortet.

    Returns:
        Dictionary mit Versandstatus und HTTP-Statuscode.
    """

    ensure_environment()

    if not report.markdown_report.strip():
        raise ValueError("Der Report ist leer und kann nicht versendet werden")

    if not EMAIL_REGEX.match(to_email or ""):
        raise ValueError("Die Zieladresse ist ungueltig")

    # Guardrail: Der Markdown-Inhalt muss weiterhin DIY-konform sein.
    if not validate_report(report.markdown_report):
        raise ValueError("Der Report scheint nicht DIY-konform zu sein")

    html_content = _render_html(report)
    if len(html_content) > MAX_EMAIL_SIZE:
        raise ValueError("Die E-Mail ueberschreitet die zulaessige Groesse")

    _LOGGER.debug("Renderte Premium-E-Mail mit %s Zeichen", len(html_content))

    payload = _build_payload(report, to_email, html_content)
    response = await _post_sendgrid(payload)

    return {
        "status": "sent" if 200 <= response.status_code < 300 else "failed",
        "status_code": response.status_code,
    }


def _render_html(report: ReportData) -> str:
    """Wandelt Markdown in ein Premium-HTML-Dokument mit Inhaltsverzeichnis um."""

    markdown = report.markdown_report
    toc_entries = _build_toc(markdown)
    html_body = md_to_html(markdown, extensions=["tables", "fenced_code", "sane_lists"])
    html_body = _inject_heading_ids(html_body, toc_entries)
    html_body = _enhance_tables(html_body)

    toc_html = _render_toc(toc_entries)
    title = _extract_title(markdown)

    styles = _premium_styles()
    html_document = f"""
    <html>
      <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <style>{styles}</style>
      </head>
      <body>
        <div class="email-container">
          <header>
            <h1>{html.escape(title)}</h1>
            <p class="intro">Premium DIY-Report – automatisch generiert, bitte lokal pruefen.</p>
          </header>
          {toc_html}
          <div class="content">
            {html_body}
          </div>
          <footer>
            <p class="footer-note">Zu lang? Kopiere den Inhalt in deinen Editor oder oeffne die HTML-Datei im Browser.</p>
          </footer>
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
    for line in markdown.splitlines():
        if line.startswith("### "):
            text = line[4:].strip()
            entries.append((text, _slugify(text), 3))
        elif line.startswith("## "):
            text = line[3:].strip()
            entries.append((text, _slugify(text), 2))
    return entries


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    return slug or "section"


def _inject_heading_ids(html_body: str, entries: List[tuple[str, str, int]]) -> str:
    updated = html_body
    for text, slug, level in entries:
        pattern = rf"<h{level}>{re.escape(text)}</h{level}>"
        replacement = f"<h{level} id=\"{slug}\">{html.escape(text)}</h{level}>"
        updated = re.sub(pattern, replacement, updated, count=1)
    return updated


def _enhance_tables(html_body: str) -> str:
    return re.sub(r"<table>", "<table class=\"table\">", html_body)


def _render_toc(entries: List[tuple[str, str, int]]) -> str:
    if not entries:
        return ""
    items = []
    for text, slug, level in entries:
        css_class = "toc-item" if level == 2 else "toc-subitem"
        items.append(f"<li class=\"{css_class}\"><a href=\"#{slug}\">{html.escape(text)}</a></li>")
    return "<nav class=\"toc\"><h2>Inhalt</h2><ul>" + "".join(items) + "</ul></nav>"


def _extract_title(markdown: str) -> str:
    for line in markdown.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return "DIY-Projekt"


def _premium_styles() -> str:
    return """
    :root {
      color-scheme: light dark;
    }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      margin: 0;
      padding: 2rem;
      background: var(--bg, #f4f6f9);
      color: var(--fg, #1f2933);
    }
    @media (prefers-color-scheme: dark) {
      body {
        --bg: #111827;
        --fg: #e5e7eb;
        background: var(--bg);
        color: var(--fg);
      }
      .email-container {
        background: #1f2933;
        box-shadow: none;
      }
    }
    .email-container {
      max-width: 960px;
      margin: 0 auto;
      background: #ffffff;
      border-radius: 16px;
      padding: 2.5rem;
      box-shadow: 0 20px 60px rgba(15, 23, 42, 0.12);
      line-height: 1.7;
    }
    header h1 {
      font-size: 2.4rem;
      margin-bottom: 0.5rem;
    }
    .intro {
      color: #64748b;
      margin-top: 0;
    }
    .toc {
      margin: 2rem 0;
      padding: 1.5rem;
      background: rgba(99, 102, 241, 0.08);
      border-radius: 12px;
    }
    .toc h2 {
      margin-top: 0;
    }
    .toc ul {
      list-style: none;
      padding-left: 1rem;
      margin: 0;
    }
    .toc li {
      margin: 0.35rem 0;
    }
    .toc a {
      color: #4338ca;
      text-decoration: none;
    }
    .toc a:hover {
      text-decoration: underline;
    }
    h2 {
      margin-top: 2.5rem;
      font-size: 1.8rem;
      border-bottom: 2px solid rgba(99, 102, 241, 0.3);
      padding-bottom: 0.4rem;
    }
    h3 {
      margin-top: 1.8rem;
      font-size: 1.3rem;
    }
    blockquote {
      border-left: 4px solid rgba(99, 102, 241, 0.6);
      padding: 0.8rem 1.2rem;
      margin: 1.2rem 0;
      background: rgba(99, 102, 241, 0.08);
      border-radius: 8px;
      font-style: italic;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      margin: 1.5rem 0;
    }
    table th,
    table td {
      border: 1px solid rgba(148, 163, 184, 0.4);
      padding: 0.75rem;
      text-align: left;
    }
    table thead {
      background: rgba(99, 102, 241, 0.12);
    }
    table tr:nth-child(even) {
      background: rgba(99, 102, 241, 0.06);
    }
    .content {
      font-size: 1.02rem;
    }
    .footer-note {
      margin-top: 3rem;
      font-size: 0.85rem;
      color: #94a3b8;
    }
    """


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


