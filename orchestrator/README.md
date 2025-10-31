# Orchestrator

## Schnellzugriff
- [Projekt-Docs-Index](../README.md#dokumentation--navigation)
- [Guards](../guards/README.md) – Input-/Output-Policies
- [Agents](../agents/README.md) – Planner/Search/Writer/Emailer

## Zweck
- Verknuepft alle Agenten zu einem asynchronen DIY-/KI-Control-Research-Flow.
- Persistiert Statusinformationen fuer Clients, die den Fortschritt abfragen.
- Orchestriert LLM-Input-/Output-Guards und behandelt Fehlerpfade zentral.

## Schnittstellen / Vertraege
- `run_job(job_id, query, email, settings_bundle)` koordiniert den vollständigen Ablauf.
- Statuszugriff via `set_status(job_id, phase, detail)` und `get_status(job_id) -> dict`.
- Phasenmodell: `queued → planning → searching → writing → email → done` (bzw. `rejected` / `error`).

## Beispielablauf
1. FastAPI ruft `run_job` in einem Hintergrund-Task auf.
2. LLM-Input-Guard (`classify_query_llm`) klassifiziert die Anfrage (`DIY`, `KI_CONTROL`, `REJECT`).
   - `REJECT` → Job stoppt sofort mit Phase `rejected` und Guard-Begruendung.
   - `DIY` / `KI_CONTROL` → Phase `planning (Kategorie: …)` wird gesetzt.
3. Planner erzeugt WebSearchPlan, Search liefert Zusammenfassungen, Writer erstellt den Report (Template-Wechsel bei `KI_CONTROL`).
4. LLM-Output-Guard (`audit_report_llm`) auditiert den Markdown. Policy-Verstöße → Phase `rejected` mit Issue-Liste.
5. Erfolgsfall: Emailer versendet den Bericht, Status endet bei `done`.

## Grenzen & Annahmen
- Statusstore ist In-Memory → fuer Multi-Prozess-Deployments persistente Alternative vorsehen.
- LLM-Guards setzen funktionierende OpenAI-API-Keys voraus; Guard-Ausfälle werden als `phase="error"` propagiert.
- Emailversand kann asynchron scheitern; Fehlertext landet im Status.

## Wartungshinweise
- Prompt-/JSON-Schema der Guards in `guards/llm_input_guard.py` und `guards/llm_output_guard.py` regelmaessig pruefen.
- Modellnamen zentral in `agents/model_settings.py` bzw. via `.env` (`PLANNER_MODEL_NAME`, `SEARCH_MODEL_NAME`, `WRITER_MODEL_NAME`, `GUARD_MODEL`) anpassen.
- Logging / Monitoring ergaenzen, sobald produktiver Betrieb geplant ist.
