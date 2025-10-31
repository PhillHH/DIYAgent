# Konfiguration

## Schnellzugriff
- [Projekt-Docs-Index](../README.md#dokumentation--navigation)
- [Agents](../agents/README.md) – Modellparameter & Defaults
- [Guards](../guards/README.md) – Kategorien & ModelSettings

## Zweck
- Lädt `.env`-Werte frühzeitig und stellt sie als Modulkonstanten (`config/settings.py`) bereit.
- Dient als zentrale Stelle, um Feature-Flags (z. B. Guard-Aktivierung, Tracing) zu steuern.

## Ladevorrang
1. Projektweite `.env` im Repository-Stamm (`../.env`).
2. Fallback: `config/.env.example` (nur wenn keine `.env` vorhanden ist).

## Wichtige Variablen
- **Credentials**: `OPENAI_API_KEY`, `SENDGRID_API_KEY`, `FROM_EMAIL`.
- **Tracing**: `OPENAI_TRACING_ENABLED`, `OPENAI_TRACE_RAW`, `LOG_DIR`, `OPENAI_WEB_TOOL_TYPE`.
- **Guards**: `LLM_GUARDS_ENABLED` (Standard: `true`), `GUARD_MODEL`, `GUARD_TEMPERATURE` (Default `0.0`).
- **Modelle**: `PLANNER_MODEL_NAME`, `SEARCH_MODEL_NAME`, `WRITER_MODEL_NAME` (Default jeweils `gpt-4o-mini`).
- **Zeit/Nutzung**: `MAX_CONCURRENCY`, `REQUEST_TIMEOUT`, `HOW_MANY_SEARCHES`, `SEARCH_CONTEXT_SIZE`.

Alle Werte werden beim Import von `config/settings.py` gelesen. Änderungen an der `.env` erfordern einen Neustart der Anwendung.

## Guard-Flags
- `LLM_GUARDS_ENABLED` sollte in Produktionsumgebungen **nicht** deaktiviert werden; ohne Guards stoppt der Orchestrator den Job.
- Guard-Modelle können separat konfiguriert werden (z. B. `gpt-4o-mini` vs. `gpt-4.1-mini`).

## Tracing
- Aktivierung via `OPENAI_TRACING_ENABLED=true` leitet Prompt/Response-Metadaten an `logs/openai.log` weiter.
- `OPENAI_TRACE_RAW=true` protokolliert vollständige Inhalte (nur lokal empfohlen).

## Tipps
- Nutze `scripts/dev.(ps1|sh)`, um sicherzustellen, dass `.env` im Projektstamm geladen wird.
- Für CI/CD separate `.env`-Dateien oder Secret Stores verwenden; `config/.env.example` als Vorlage pflegen.

