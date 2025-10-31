# Agents

## Zweck
- Planner, Search, Writer und Emailer bilden den fachlichen Kern der DIY-Recherche.
- KI-Modelle (OpenAI) werden genutzt, um strukturiert zu planen, Inhalte zusammenzufassen und Berichte zu verfassen.
- Emailer verpackt den Bericht in HTML und versendet ihn ueber SendGrid.

## Schnittstellen / Vertraege
- `plan_searches(query, settings) -> WebSearchPlan`
- `perform_searches(plan, settings) -> list[str]`
- `write_report(query, search_results, settings, category=None) -> ReportData`
- `send_email(report, to_email) -> dict`
- Alle Funktionen werfen `ValueError` bei Guardrail-Verletzungen und propagieren `RuntimeError` fuer externe Fehler.

## Writer-Varianten (DIY vs. KI_CONTROL)
- **DIY**: Premium-Markdown mit Executive Summary, Material-Tabellen, Schrittfolgen, Sicherheit, Premium-Laminat, FAQ.
- **KI_CONTROL**: Analysebericht zu Steuerbarkeit/Evaluierung von KI (Abschnitte: Ziel & Kontext, Steuerbare Aspekte, Risiken, Metriken, Evaluationsplan, Governance, Empfehlungen & Roadmap, FAQ).
- Die Kategorie wird vom LLM-Input-Guard bestimmt und in `run_job` weitergereicht.

## Beispielablauf
1. LLM-Input-Guard klassifiziert die Anfrage (`DIY`, `KI_CONTROL`, `REJECT`).
2. Planner (OpenAI, `gpt-4o-mini`) erzeugt Suchaufgaben.
3. Search fasst pro Item 2–3 Absätze zusammen (Temperatur 0.3), paralleler Aufruf durch `AsyncLimiter` begrenzt.
4. Writer erstellt JSON-Report und validiert Inhalte (DIY-Gruen, KI_CONTROL-ohne DIY-Heuristik).
5. LLM-Output-Guard prueft den Markdown auf Policies, danach versendet der Emailer das HTML.

## Grenzen & Annahmen
- DIY-Erkennung erfolgt primär über den LLM-Input-Guard; bei Fallback greift eine Keyword-Heuristik.
- OpenAI-Modelle liefern teilweise Codeblöcke → Parser entfernt Begrenzungen.
- SendGrid-Key muss Mail-Send-Rechte haben; Absenderadresse muss verifiziert sein.
- Summaries basieren auf Modellwissen, solange kein WebSearch-Tool aktiv ist.

## Wartungshinweise
- Modellnamen/Parameter zentral in `agents/model_settings.py` aendern.
- Guardrail-Prompts in `guards/llm_*` regelmaessig evaluieren (siehe Tracing-Logs).
- Bei Parser-Fehlern (JSON) Prompts verfeinern oder `_extract_json_block` erweitern.
