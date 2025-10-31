# Guards

## Schnellzugriff
- [Projekt-Docs-Index](../README.md#dokumentation--navigation)
- [Orchestrator](../orchestrator/README.md) – Phasen & Guard-Einbindung
- [Agents](../agents/README.md) – Writer-Template je Kategorie

## Zweck
- Stellt Eingabe- und Ausgabepruefungen fuer den DIY-/KI-Control-Flow bereit.
- Klassifiziert Nutzeranfragen und auditiert Berichte ausschliesslich ueber LLMs.

## Schnittstellen / Vertraege
- `classify_query_llm(query, settings) -> InputGuardResult` – Kategorien `DIY`, `KI_CONTROL`, `REJECT`.
- `audit_report_llm(query, report_md, settings) -> OutputGuardResult` – Policy-Check fuer finalen Markdown (`allowed`, `issues`, `category`).

## Beispielablauf
1. `run_job` ruft `classify_query_llm` auf. `REJECT` → Job endet mit Status „rejected“ und Begruendung.
2. Bei `DIY` oder `KI_CONTROL` durchlaeuft der Flow Planung, Recherche, Writer (ggf. Template-Wechsel fuer KI_CONTROL).
3. Anschliessend prueft `audit_report_llm` den Markdown. `allowed=False` → Job stoppt mit „Policy: …“.

## LLM-Input-Guard
- Prompt klassifiziert eindeutig in `DIY`, `KI_CONTROL`, `REJECT` (Meta-Themen wie Guardrails fallen unter `KI_CONTROL`).
- Antwort wird als JSON-Schema eingefordert; Parsing-Fehler oder API-Probleme fuehren zu `RuntimeError("Input-Guard nicht verfügbar")`.

## LLM-Output-Guard
- Bewertet den finalen Markdown hinsichtlich Sicherheits-/Policy-Anforderungen.
- Erlaubt DIY-Inhalte sowie Meta-Analysen zur KI-Steuerung; verbietet riskante Anleitungen ohne Fachkraft/Warnhinweise, medizinische & finanzielle Beratung, PII.
- Liefert JSON (`allowed`, `category`, `issues`); Fehler resultieren in `RuntimeError("Output-Guard nicht verfügbar")`.

## Grenzen & Annahmen
- LLM-Guards setzen eine funktionierende OpenAI-API voraus; bei Ausfall bricht die Pipeline mit `phase="error"` ab (kein heuristischer Fallback mehr).
- Prompt-Feintuning ist entscheidend, um Fehlklassifikationen zu vermeiden. Tracing (`OPENAI_TRACE_*`) hilft beim Debugging.

## Wartungshinweise
- Regelmässig Prompts und Antwortschemas pruefen (z. B. via OpenAI-Traces).
- Bei Modellwechsel Guard-Modelle in `.env` (`GUARD_MODEL`, `GUARD_TEMPERATURE`) anpassen.
