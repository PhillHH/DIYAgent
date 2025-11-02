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
- `perform_searches(plan, settings, *, user_query, category=None) -> tuple[list[str], list[ProductItem]]`
- `write_report(query, search_results, settings, category=None, product_results=None) -> ReportData`
- `send_email(report, to_email, product_results=None, brand=None, meta=None) -> dict`

Alle Funktionen werfen `ValueError` bei Guardrail-Verletzungen und propagieren `RuntimeError` fuer externe Fehler (z. B. API-Timeouts).

## Writer-Varianten (DIY vs. KI_CONTROL)
- **DIY**: Premium-Markdown mit Meta-Zeile, internem Inhaltsverzeichnis (nur `#anker`), Vorbereitung, Einkaufsliste Bauhaus (Tabelle mit Links), Schritt-für-Schritt inklusive Prüfkriterien, Qualität & Sicherheit, Zeit & Kosten sowie optionalen Upgrades/Pflege. FAQ am Ende, Laminat-Block entfällt.
- **KI_CONTROL**: Governance-/Evaluationsbericht mit Sektionen zu Ziel & Kontext, steuerbaren Aspekten, Risiken, Metriken, Testplan, Governance und Roadmap.
- Die Kategorie wird ausschließlich vom LLM-Input-Guard geliefert und unverändert bis zum Writer durchgereicht.

## Beispielablauf
1. LLM-Input-Guard klassifiziert die Anfrage (`DIY`, `KI_CONTROL`, `REJECT`).
2. Planner (Standardmodell `gpt-4o-mini`) erzeugt ein `WebSearchPlan`-Objekt.
3. Search führt parallele OpenAI-Websuchen durch, fasst Ergebnisse zusammen und extrahiert zusätzliche Bauhaus-Produkte (`ProductItem`).
4. Writer generiert `ReportData` im JSON-Format, ersetzt die Sektion "Einkaufsliste (Bauhaus-Links)" deterministisch durch geprüfte Bauhaus-Links und erzwingt interne Anker.
5. LLM-Output-Guard auditiert den Markdown (Händler-Links erlaubt; lediglich `mail.google.com` wird blockiert).
6. Emailer rendert ein gebrandetes HTML (Gradient, Dark-Mode, CTA) und versendet es via SendGrid.

## Grenzen & Annahmen
- Die Guards sind harte Abhängigkeiten – fällt der OpenAI-Call aus, bricht der Gesamtjob mit `status="error"` ab.
- Modelle liefern teilweise Codeblöcke → `_extract_json_block` in Planner/Writer entfernt Einbettungen robust.
- SendGrid erfordert verifizierte Absenderadresse; Fehler (401/403) werden bis zum Orchestrator propagiert.
- Websuche setzt das OpenAI-Web-Tool voraus; Response-Größen orientieren sich an `SEARCH_CONTEXT_SIZE`.
- Produktlinks werden dedupliziert und von Tracking-Parametern befreit; nur Bauhaus-Domains werden akzeptiert.

## Wartungshinweise
- Modellnamen und Temperatureinstellungen zentral in `model_settings.py` pflegen (inkl. `DEFAULT_GUARD`).
- Prompt-Anpassungen in `planner.py`, `search.py`, `writer.py` sowie `guards/llm_*` stets gemeinsam testen (siehe `tests/unit`).
- Bei JSON-Parsing-Problemen `_extract_json_block` erweitern oder Response-Formate strenger via `response_format` definieren.
