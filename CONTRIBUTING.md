# CONTRIBUTING

## Code-Stil
- Python 3.11+, Black-kompatible Formatierung, docstrings auf Deutsch.
- Async-Funktionen bevorzugen, wenn externe I/O vorhanden ist.
- Guardrails nicht entfernen, sondern bei Bedarf erweitern.

## Tests
- Vor jedem PR `python -m pytest tests/unit tests/integration` ausführen.
- Neue Features mit passenden Unit- oder Integrationstests absichern.

## Commits
- Aussagekräftige Commit-Botschaften (Deutsch oder Englisch, keine Secrets).
- Kleine, logisch zusammenhängende Änderungen pro Commit.

## Secrets
- Keine API-Keys oder Passwörter einchecken.
- `.env` in lokalen Umgebungen halten; Beispielformate in `config/.env.example` pflegen.

## Review-Hinweise
- Prüfen, ob DIY-Guardrails weiterhin greifen.
- Bei Modellwechseln stets `agents/model_settings.py` und Dokumentation aktualisieren.
