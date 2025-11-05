# Tests

## Schnellzugriff
- [Projekt-Docs-Index](../README.md#dokumentation--navigation)
- [Agents](../agents/README.md) – Testrelevante Schnittstellen
- [Guards](../guards/README.md) – Kategorien & Policy-Annahmen

## Struktur
- `tests/unit/` – Schnelle Unit-Tests für Agents, Guards, Tracing und Writer/Emailer.
- `tests/integration/` – API-/Pipeline-Integration (inkl. Guard-Flow & E2E-Orchestrierung).
- `tests/test_async.py` – Basistest für Async-Helfer (historisch bedingt außerhalb der Unterordner).

## Ausführung
```bash
python -m pytest tests/unit
python -m pytest tests/integration
# Komplettlauf
python -m pytest
```

CI sollte stets beide Suites ausführen, bevor produktive Keys genutzt werden.

## Besonderheiten
- **LLM-Guards**: `tests/unit/test_llm_input_guard.py`, `test_llm_output_guard.py`, `test_guard_links_toc.py` prüfen Klassifikation, Policy-Validierung und blockieren weiterhin `mail.google.com`-Links.
- **Pipeline & Einkaufsliste**: `tests/unit/test_pipeline_products.py`, `test_writer_no_placeholders.py`, `test_email_links.py` sichern den Bauhaus-Link-Fluss, das strukturierte `ReportPayload` und verhindern Platzhalter-Links.
- **Premium-Report & Branding**: `tests/unit/test_email_branding.py`, `test_email_links.py`, `test_writer_sections.py` validieren Template, Einkaufsliste (Bauhaus-Links) und Prompt-Struktur.
- **Produktsuche**: `tests/unit/test_search_products.py` sichert Parsing & Filterung der Bauhaus-Ergebnisse ab.
- **End-to-End**: `tests/integration/test_pipeline.py` simuliert den kompletten Flow inkl. Statuspayload (Einkaufsliste) und Guard-Ergebnissen.

## Hinweise
- Neue Features sollten mindestens einen Unit-Test erhalten; für Guard-/Orchestrator-Änderungen zusätzlich Integrationstests ergänzen.
- Mock-Dateien und Fixtures liegen in den jeweiligen Testmodulen, um Abhängigkeiten schlank zu halten.

