# CONTRIBUTING

## Code-Stil
- Python 3.11+, Black-kompatible Formatierung, docstrings auf Deutsch.
- Async-Funktionen bevorzugen, wenn externe I/O vorhanden ist.
- Guardrails nicht entfernen, sondern bei Bedarf erweitern.

## Tests
- Vor jedem PR `python -m pytest tests/unit tests/integration` ausführen (Details siehe [`tests/README.md`](tests/README.md)).
- Neue Features mit passenden Unit- oder Integrationstests absichern.

## Commits
- Aussagekräftige Commit-Botschaften (Deutsch oder Englisch, keine Secrets).
- Kleine, logisch zusammenhängende Änderungen pro Commit.

## Secrets
- Keine API-Keys oder Passwörter einchecken.
- `.env` in lokalen Umgebungen halten; Beispielformate in `config/.env.example` pflegen.

## Review-Hinweise
- Prüfen, ob DIY-/KI-Control-Guardrails weiterhin greifen (siehe [`guards/README.md`](guards/README.md)).
- Bei Modellwechseln stets `agents/model_settings.py` und Dokumentation aktualisieren (`agents/README.md`, `config/README.md`).
