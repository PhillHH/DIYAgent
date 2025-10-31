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
- **LLM-Guards**: `tests/unit/test_llm_input_guard.py` und `tests/unit/test_llm_output_guard.py` mocken OpenAI-Responses (DIY/KI_CONTROL/REJECT, erlaubte vs. geblockte Reports).
- **Premium-Report**: `tests/unit/test_emailer_rendering.py` stellt sicher, dass HTML-Features (Inhaltsverzeichnis, Tabellenklassen) nach Template-Änderungen bestehen bleiben.
- **End-to-End**: `tests/integration/test_pipeline.py` simuliert den kompletten Flow inkl. Statusübergängen und Guard-Ergebnissen.

## Hinweise
- Neue Features sollten mindestens einen Unit-Test erhalten; für Guard-/Orchestrator-Änderungen zusätzlich Integrationstests ergänzen.
- Mock-Dateien und Fixtures liegen in den jeweiligen Testmodulen, um Abhängigkeiten schlank zu halten.

