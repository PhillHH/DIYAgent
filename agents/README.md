# Agents

## Zweck
- Planner, Search, Writer und Emailer bilden den fachlichen Kern der DIY-Recherche.
- KI-Modelle (OpenAI) werden genutzt, um strukturiert zu planen, Inhalte zusammenzufassen und Berichte zu verfassen.
- Emailer verpackt den Bericht in HTML und versendet ihn ueber SendGrid.

## Schnittstellen / Vertraege
- `plan_searches(query, settings) -> WebSearchPlan`
- `perform_searches(plan, settings) -> list[str]`
- `write_report(query, search_results, settings) -> ReportData`
- `send_email(report, to_email) -> dict`
- Alle Funktionen werfen `ValueError` bei Guardrail-Verletzungen und propagieren `RuntimeError` fuer externe Fehler.

## Beispielablauf
1. Planner (OpenAI, `gpt-4o-mini`) erzeugt exakt `HOW_MANY_SEARCHES` Eintraege.
2. Search fasst pro Item 2–3 Absätze zusammen (Temperatur 0.3), paralleler Aufruf durch `AsyncLimiter` begrenzt.
3. Writer erstellt JSON-Report (Kurzfassung, Markdown, Nachfragen) und prueft anschliessend DIY-Guardrail.
4. Emailer wandelt Markdown in einfaches HTML, validiert Groessenlimit und sendet via SendGrid.

## Grenzen & Annahmen
- DIY-Erkennung erfolgt per Keyword-Heuristik (`guards/input_guard` / `guards/output_guard`).
- OpenAI-Modelle liefern teilweise Codeblöcke → Parser entfernt Begrenzungen.
- SendGrid-Key muss Mail-Send-Rechte haben; Absenderadresse muss verifiziert sein.
- Summaries basieren auf Modellwissen, solange kein WebSearch-Tool aktiv ist.

## Wartungshinweise
- Modellnamen/Parameter zentral in `agents/model_settings.py` aendern.
- Guardrail-Schluesselwoerter regelmaessig validieren.
- Bei Parser-Fehlern (JSON) Prompts verfeinern oder `model_validate_json`-Pfad erweitern.
