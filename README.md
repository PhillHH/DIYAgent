# Deep Research Agent

## Zweck
- KI-gestuetztes System fuer heimwerkerbezogene Recherche, Zusammenfassung und E-Mail-Versand.
- Modulare Agenten (Planer, Rechercheur, Autor, E-Mailer) bilden einen vollständigen End-to-End-Flow.
- DIY-Guardrails stellen sicher, dass fachfremde Anfragen automatisch abgelehnt werden.

## Architektur (Textdiagramm)
```
Client -> FastAPI (/start_research) -> Orchestrator.run_job
  |-> Planner (OpenAI) -> WebSearchPlan
  |-> Search (OpenAI, parallel) -> Zusammenfassungen
  |-> Writer (OpenAI) -> ReportData
  |-> Guards -> Validierung DIY/Markdown
  |-> Emailer (SendGrid) -> Versand
Status-Store <- FastAPI (/status/{job_id})
```

## Setup
1. Repository klonen, Python 3.11+ verwenden.
2. Virtuelle Umgebung anlegen und aktivieren:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
3. Abhaengigkeiten installieren:
   ```powershell
   pip install -e .
   ```
4. `.env` im Projektstamm erstellen (oder aus `.env.example` kopieren) und mindestens `OPENAI_API_KEY`, `SENDGRID_API_KEY`, `FROM_EMAIL` setzen.
5. Optional weitere Parameter in `config/settings.py` bzw. `agents/model_settings.py` justieren.

## Tests
- Vollsuite: `python -m pytest tests/unit tests/integration`
- Einzeltest, z. B. Planner: `python -m pytest tests/unit/test_planner.py`

## End-to-End-Ablauf (lokal)
1. FastAPI starten: `uvicorn api.main:app --reload`
2. Probelauf: `python scripts/e2e_probe.py --email deine.mail@example.com`
3. Skript pollt `/status/{job_id}` und zeigt Phasen an; Exit-Code `0` bei Erfolg, sonst `1`.

## Lokaler Start (Venv)
- Verwende die Hilfsskripte, damit uvicorn immer das Projekt-Venv nutzt:
  - PowerShell: `scripts\dev.ps1`
  - POSIX (bash/zsh): `./scripts/dev.sh`
- Somit wird `uvicorn api.main:app --reload` mit aktivierter `.venv`-Umgebung gestartet; ohne dies kann `ModuleNotFoundError: No module named 'markdown'` auftreten, weil der Reload-Prozess sonst den globalen Python-Interpreter nutzt.
- Hinweis: Globale `PYTHONPATH`-Änderungen oder `use-pep582`-Flags sollten deaktiviert bleiben, damit die Venv-Erkennung konsistent funktioniert.

## Troubleshooting
- **OpenAI/SENDGRID-Key fehlt** → `.env` pruefen; Fehlermeldung nennt die Variablen.
- **Modell liefert `REJECT`** → Anfrage konkreter als DIY formulieren (z. B. Werkzeuge, Materialien erwaehnen).
- **SendGrid 401** → API-Key oder verifizierte Absenderadresse pruefen.
- **Timeout** → Netzwerkverbindung, Rate-Limit, `MAX_CONCURRENCY` reduzieren.
- **Logs** → FastAPI-Console sowie SendGrid Activity Dashboard kontrollieren.

## Wartungshinweise
- Neue Modelle zentral in `agents/model_settings.py` anpassen.
- LLM-Guard-Prompts in `guards/llm_input_guard.py` und `guards/llm_output_guard.py` regelmaessig pruefen und bei Bedarf tweaken.
- Tests in CI einbinden, bevor produktive Keys verwendet werden.

## OpenAI-Tracing (Prototyp)
- Aktivierbar ueber `.env`:
  - `OPENAI_TRACE_ENABLED=true` (Tracing einschalten)
  - `OPENAI_TRACE_RAW=true` (Prompt/Output im Klartext loggen; nur lokal verwenden!)
- Logs landen als JSON-Zeilen in `logs/openai.log` (`call_name`, Dauer, Tokenschaetzung, Kosten).
- In Produktion `OPENAI_TRACE_RAW=false` setzen, da Rohdaten sensible Informationen enthalten koennen.
- Drei Eintraege pro Job (Planner, Search je Item, Writer), Suchphase kann mehrere Logs erzeugen.

## OpenAI Websuche & Traces
- Aktivierung:
  - `.env`: `OPENAI_TRACING_ENABLED=true`, optional `OPENAI_TRACE_RAW=true` fuer Klartext-Logs (nur lokal!).
  - Search-Agent nutzt das OpenAI-Webtool (`tools=[{"type":"web"}]`, `tool_choice="auto"`). Optional (`OPENAI_WEB_TOOL_TYPE`) kann zwischen `web_search_preview` und anderen Preview-Versionen gewechselt werden.
- Troubleshooting: HTTP 400 *unknown_parameter* → Tool-Konfiguration pruefen; Fallback ohne `tool_choice` sowie alternative Tool-Typen (z. B. `web_search_preview_2025_03_11`) werden automatisch getestet.
- Erwartete Anzeige: Im OpenAI-Dashboard unter “Traces” erscheinen Planner → Search (je Item) → Writer inkl. Tool-Schritten.
- Datenschutz: Kompletttraces koennen sensible Inhalte enthalten. In Produktion `OPENAI_TRACE_RAW=false` oder Tracing abschalten.

## Premium-E-Mail-Report
- Aufbau: Writer generiert 1.800–2.500 Woerter mit Premium-Struktur (Executive Summary, Tabellen fuer Material/Zeiten, Sicherheitskapitel, Premium-Laminat-Vergleich, FAQ).
- Rendering: Emailer wandelt Markdown in typografisch formatiertes HTML mit Inhaltsverzeichnis, Tabellen-Styles (class="table"), Dark-Mode-Optimierung und Hinweisblöcken.
- Konfiguration: `.env` optional `OPENAI_WEB_TOOL_TYPE` fuer Websuche, `OPENAI_TRACING_ENABLED` fuer Plattform-Traces, `OPENAI_TRACE_RAW` fuer lokale Loginspektion.
- Limits & Performance: MAX_EMAIL_SIZE 500 KB; lange Inhalte werden nicht gekürzt. Bei grossen Projekten kann das Rendern einige Sekunden dauern.
- Troubleshooting: 400er von OpenAI → Tool-Type pruefen (`web_search_preview`, `web_search_preview_2025_03_11`), bei SendGrid-401 API-Key und Berechtigungen validieren. Beispiel-Screenshot folgt im separaten `docs/`-Ordner.

## LLM-Guards
- Input: `classify_query_llm` klassifiziert Anfragen (`DIY`, `KI_CONTROL`, `REJECT`). REJECT stoppt den Job sofort, KI_CONTROL aktiviert das Governance-Template im Writer.
- Output: `audit_report_llm` prueft den finalen Markdown gegen Policies (DIY/KI-Control erlaubt, riskante Inhalte werden abgewiesen). Bei Guard-Ausfall bricht der Job mit `phase="error"` ab.
- Statusmeldungen dokumentieren die Kategorie sowie eventuelle Policy-Issues im `detail`-Feld.

