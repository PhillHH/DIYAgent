# Agents

## Schnellzugriff
- [Orchestrator-Flow](../orchestrator/README.md) – Wie Planner, Search, Writer & Emailer kombiniert werden
- [Guards](../guards/README.md) – Input-/Output-Validierung inkl. Kategorien
- [Model-Settings](model_settings.py) – Standardparameter der OpenAI-Clients

## Zweck
- Planner, Search, Writer und Emailer bilden den fachlichen Kern der DIY-/KI-Control-Recherche.
- KI-Modelle (OpenAI) planen Suchstrategien, konsolidieren Webinhalte und erzeugen Premium-Markdown-Reports.
- Der Emailer rendert den Report in hochwertiges HTML und versendet ihn via SendGrid.

## Schnittstellen / Vertraege
- `plan_searches(query, settings) -> WebSearchPlan`
- `perform_searches(plan, settings) -> list[str]`
- `write_report(query, search_results, settings, category=None) -> ReportData`
- `send_email(report, to_email) -> dict`

Alle Funktionen werfen `ValueError` bei Guardrail-Verletzungen und propagieren `RuntimeError` fuer externe Fehler (z. B. API-Timeouts).

## Writer-Varianten (DIY vs. KI_CONTROL)
- **DIY**: Premium-Markdown mit Executive Summary, Material-/Kosten-Tabellen, Schrittfolgen, Sicherheitsabschnitten, Premium-Laminat-Optionen, FAQ und Pflegehinweisen.
- **KI_CONTROL**: Governance-/Evaluationsbericht mit Sektionen zu Ziel & Kontext, steuerbaren Aspekten, Risiken, Metriken, Testplan, Governance und Roadmap.
- Die Kategorie wird ausschließlich vom LLM-Input-Guard geliefert und unverändert bis zum Writer durchgereicht.

## Beispielablauf
1. LLM-Input-Guard klassifiziert die Anfrage (`DIY`, `KI_CONTROL`, `REJECT`).
2. Planner (Standardmodell `gpt-4o-mini`) erzeugt ein `WebSearchPlan`-Objekt.
3. Search führt parallele OpenAI-Websuchen durch, fasst Ergebnisse als Freitext zusammen und extrahiert Kernbefunde.
4. Writer generiert `ReportData` im JSON-Format (Markdown + Kurzfassung + 4–6 Follow-up-Fragen).
5. LLM-Output-Guard auditiert den Markdown gegen Policy-Anforderungen.
6. Emailer rendert und versendet das HTML; SendGrid-Antwort wird an den Orchestrator zurückgegeben.

## Grenzen & Annahmen
- Die Guards sind harte Abhängigkeiten – fällt der OpenAI-Call aus, bricht der Gesamtjob mit `status="error"` ab.
- Modelle liefern teilweise Codeblöcke → `_extract_json_block` in Planner/Writer entfernt Einbettungen robust.
- SendGrid erfordert verifizierte Absenderadresse; Fehler (401/403) werden bis zum Orchestrator propagiert.
- Websuche setzt das OpenAI-Web-Tool voraus; Response-Größen orientieren sich an `SEARCH_CONTEXT_SIZE`.

## Wartungshinweise
- Modellnamen und Temperatureinstellungen zentral in `model_settings.py` pflegen (inkl. `DEFAULT_GUARD`).
- Prompt-Anpassungen in `planner.py`, `search.py`, `writer.py` sowie `guards/llm_*` stets gemeinsam testen (siehe `tests/unit`).
- Bei JSON-Parsing-Problemen `_extract_json_block` erweitern oder Response-Formate strenger via `response_format` definieren.
