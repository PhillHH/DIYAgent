# Orchestrator

## Zweck
- Verknuepft alle Agenten zu einem asynchronen DIY-Research-Flow.
- Persistiert Statusinformationen fuer Clients, die den Fortschritt abfragen.
- Behandelt Guardrails (DIY-Pruefungen) und Fehlerpfade zentral.

## Schnittstellen / Vertraege
- `run_job(job_id, query, email, settings_bundle)` koordiniert den vollständigen Ablauf.
- Statuszugriff via `set_status(job_id, phase, detail)` und `get_status(job_id) -> dict`.
- Phasenmodell: `queued → planning → searching → writing → email → done` (oder `rejected/error`).

## Beispielablauf
1. FastAPI ruft `run_job` in einem Hintergrund-Task auf.
2. Planner erzeugt WebSearchPlan und aktualisiert Phase `planning` → `searching`.
3. Search liefert Zusammenfassungen; Writer erstellt Report; Emailer verschickt Ergebnis.
4. Erfolgsfall endet mit `done`, Ablehnung / Fehler werden ebenfalls im Status abgelegt.

## Grenzen & Annahmen
- Statusstore ist In-Memory → für Multi-Prozess-Deployments persistenten Store vorsehen.
- Guardrails basieren auf heuristischen Keyword-Pruefungen.
- Emailversand kann asynchron scheitern; Fehlertext wird im Status gespeichert.

## Wartungshinweise
- Neue Phasen konsequent in `status.py` und `README.md` dokumentieren.
- Bei Modellwechseln SettingsBundle aktualisieren oder per Dependency Injection ersetzen.
- Logging / Monitoring ergaenzen, wenn Produktionsbetrieb geplant ist.
