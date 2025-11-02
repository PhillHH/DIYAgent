# CHANGELOG

Alle nennenswerten Änderungen an diesem Projekt werden hier dokumentiert. Format angelehnt an [Keep a Changelog](https://keepachangelog.com/de/1.0.0/).

## [Unreleased]
- Dokumentations-Refresh inkl. globalem Docs-Index und Querverweisen.
- Neue README-Dateien für `config/`, `util/` und `tests/`.
- Initialer `CHANGELOG.md`.
- Neue `tests/unit/test_pipeline_products.py`, `test_writer_no_placeholders.py`, `test_email_links.py` sichern den Bauhaus-Link-Fluss und verhindern Platzhalter-Links.
- Projektbranding auf "Home Task AI" aktualisiert (Frontend, E-Mail-Template, Dokumentation).

## [2025-11-01]
### Hinzugefügt
- Branded Premium-E-Mail-Template mit Header, Gradient, Dark-Mode und CTA; Bauhaus-Einkaufsliste als HTML-Sektion.
- LLM-gestützte Produktsuche (Bauhaus) inkl. Tracking-Filter und Übergabe an Writer/Emailer.
- Status-Payload (`payload.email_links`) sowie E2E-Probe, die Bauhaus-Links im Versand überprüft.
- Zusätzliche Tests (`test_email_branding`, `test_email_links`, `test_search_products`, `test_guard_links_toc`, `test_writer_sections`).
- Neues `models/types.py` mit `ProductItem` sowie URL-Sanitizer für Bauhaus-Links; Writer/Emailer erzeugen nur noch reale Einkaufslisten ohne Platzhalter.

### Geändert
- Writer-Prompt: Internes Inhaltsverzeichnis (nur `#`-Anker), Einkaufsliste Bauhaus, Prüfkriterien je Schritt, Laminat-Block entfernt.
- Output-Guard: Händler-Links erlaubt, nur `mail.google.com` wird blockiert; OpenAI-Tracing markiert `search_products`/`writer_email`.
- Dokumentation (README, Agents, Guards, API, Frontend, Scripts, Tests) um Branding-, Produktlink- und ToC-Richtlinien erweitert.

## [2025-10-31]
### Hinzugefügt
- Premium-E-Mail-Report mit High-End-Markdown-Template und HTML-Renderer (Typografie, TOC, Dark Mode).
- LLM-basierte Input- und Output-Guards (JSON-Schema, keine heuristischen Fallbacks).
- KI_CONTROL-Writer-Template für Governance-/Evaluationsberichte.
- Dev-Skripte `scripts/dev.ps1` & `scripts/dev.sh`, um Uvicorn stets im Projekt-Venv zu starten.
- Vite + React Frontend mit Polling, Toasts, Tailwind v4 und modernem UI.

### Geändert
- Planner/Search/Writer nutzen gemeinsame OpenAI-Tracing-Helfer (`util/openai_tracing.py`).
- Emailer generiert ästhetische HTML-Mails (Tabellenstyling, Inhaltsverzeichnis, Dark-Mode-Farben).
- Konfigurationswerte (`config/settings.py`) erweitert um Guard-/Tracing-Flags.

### Entfernt
- Heuristische DIY-Prüfpfade – Guards verlassen sich vollständig auf LLM-Klassifikationen.

