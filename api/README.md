# API

## Schnellzugriff
- [Projekt-Docs-Index](../README.md#dokumentation--navigation)
- [Script-Dokumentation](../scripts/README.md) – Dev-Skripte & E2E-Probe
- [Orchestrator](../orchestrator/README.md) – Phasen & Statusdetails

## Zweck
- Bietet eine schlanke FastAPI-Schnittstelle von Home Task AI, um Heimwerker- und KI-Control-Recherchen zu starten und den Fortschritt abzufragen.

## Schnittstellen / Vertraege
- `POST /start_research` – Body: `{ "query": str, "email": str }` → Antwort `{ "job_id": str }`.
- `GET /status/{job_id}` – Antwort `{ "job_id": str, "phase": str, "detail": Optional[str], "payload": Optional[dict] }`.
- `payload` enthält z. B. `{ "email_links": [...], "email_preview": "...", "product_results": [...] }`, sobald der Versand erfolgreich war.
- Phasen: `queued → planning → searching → writing → email → done`. Fehlerpfade führen zu `rejected` (Guard) oder `error` (Systemfehler).

## Beispielablauf
```http
POST /start_research
{
  "query": "Laminat im Wohnzimmer verlegen",
  "email": "user@example.com"
}
-> {"job_id": "uuid"}

GET /status/uuid
-> {
     "job_id": "uuid",
     "phase": "done",
     "detail": null,
     "payload": {
       "email_links": ["https://www.bauhaus.info/..."],
       "email_preview": "<html>...",
       "product_results": [{"title": "...", "url": "https://www.bauhaus.info/..."}]
     }
   }
```

## CORS & Lokaler Betrieb
- Dev-Frontend läuft standardmäßig auf `http://localhost:5173` (siehe `frontend/README.md`).
- `api/main.py` erlaubt `http://localhost:5173` sowie `http://127.0.0.1:5173` via `CORSMiddleware` (`allow_origin_regex`).
- Verwende `scripts/dev.ps1` bzw. `scripts/dev.sh`, um Uvicorn innerhalb des Projekt-Venv auf Port 8005 zu starten (`uvicorn api.main:app --reload --port 8005`).

## Grenzen & Annahmen
- Kein Authentifizierungsmechanismus – vor produktivem Einsatz ergänzen.
- Status ist eventually consistent; Pollingintervall gemäß Skript (`scripts/e2e_probe.py`).
- Fehlerdetails sind im `detail`-Feld in Klartext enthalten; Zusatzdaten (z. B. Einkaufsliste) erscheinen in `payload`.

## Wartungshinweise
- Bei neuen Phasen oder Fehlertypen Beispiele in Dokumentation aktualisieren.
- OpenAPI-Schema (`app.openapi()`) kann für API-Clients exportiert werden.
