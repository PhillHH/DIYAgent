# CHANGELOG

Alle nennenswerten Änderungen an diesem Projekt werden hier dokumentiert. Format angelehnt an [Keep a Changelog](https://keepachangelog.com/de/1.0.0/).

## [Unreleased]
- Dokumentations-Refresh inkl. globalem Docs-Index und Querverweisen.
- Neue README-Dateien für `config/`, `util/` und `tests/`.
- Initialer `CHANGELOG.md`.

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

