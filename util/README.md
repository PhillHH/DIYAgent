# Util

## Schnellzugriff
- [Projekt-Docs-Index](../README.md#dokumentation--navigation)
- [Tests](../tests/README.md) – Relevante Einheiten
- [Agents](../agents/README.md) – Stellen, die Tracing/Parsing nutzen

Hilfsfunktionen rund um OpenAI-Integrationen und Tracing.

## Module
- **`openai_tracing.py`**
  - Stellt `traced_completion(call_name, model, payload, executor)` bereit.
  - Loggt Dauer, geschätzte Token-Kosten sowie (optional) Roh-Prompts in `logs/openai.log`.
  - Unterstützt OpenAI Platform Traces via `OPENAI_TRACING_ENABLED` / `OPENAI_TRACE_RAW` (siehe [`config/README.md`](../config/README.md)).
  - Calls `search_products` und `writer_email` werden mit `highlight=true` markiert, um Bauhaus-Recherche und Writer-HTML schnell wiederzufinden.

- **`openai_response.py`**
  - Enthält `extract_output_text` zum robusten Extrahieren von Text aus OpenAI-Responses (inkl. Tool-Calls, JSON-Objekten, Chat-Bodies).
  - `_extract_json_block` schneidet Markdown-Codefences oder zusätzliche Präfixe ab, damit JSON-Parsing stabil bleibt.

## Verwendung
- Planner, Search und Writer rufen `traced_completion` auf, um alle LLM-Interaktionen zu bündeln und Nachvollziehbarkeit sicherzustellen.
- Guards (Input/Output) nutzen dieselbe Infrastruktur, damit Fehlerfälle im Log sichtbar sind.
- Bei Anpassungen an OpenAI-Clients zuerst hier Änderungen vornehmen, anschließend betroffene Tests (`tests/unit/test_openai_tracing_raw.py`, `tests/unit/test_search_payload.py`) aktualisieren.

