# Frontend (Placeholder)

## Zweck
- Reservierter Platz fuer ein kuenftiges Web-UI zum Starten und Monitoren von Jobs.

## Schnittstellen / Vertraege
- Geplante API-Aufrufe: `POST /start_research`, `GET /status/{job_id}`.
- Polling-Intervall voraussichtlich 2 Sekunden, angelehnt an `scripts/e2e_probe.py`.

## Beispielablauf
- Nutzer gibt Query + E-Mail ein → UI sendet POST-Request → zeigt Job-ID + Statuspolling.

## Grenzen & Annahmen
- Noch keine Implementierung; Validierung und UX folgen im späteren Projektstand.
- Backend muss laufen und CORS-Regeln definieren.

## Wartungshinweise
- Bei Start des UI gelieferten Abschnitt aktualisieren.
- UX-Richtlinien (Guardrails sichtbar machen, Fehlermeldungen deutschsprachig) dokumentieren, sobald umgesetzt.

