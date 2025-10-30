# API

## Zweck
- Bietet eine schlanke FastAPI-Schnittstelle, um DIY-Recherchen zu starten und den Fortschritt abzufragen.

## Schnittstellen / Vertraege
- `POST /start_research` – Body: `{ "query": str, "email": str }` → Antwort `{ "job_id": str }`.
- `GET /status/{job_id}` – Antwort `{ "job_id": str, "phase": str, "detail": Optional[str] }`.

## Beispielablauf
```http
POST /start_research
{
  "query": "Laminat im Wohnzimmer verlegen",
  "email": "user@example.com"
}
-> {"job_id": "uuid"}

GET /status/uuid
-> {"job_id": "uuid", "phase": "writing", "detail": null}
```

## Grenzen & Annahmen
- Kein Authentifizierungsmechanismus – vor produktivem Einsatz ergänzen.
- Status ist eventually consistent; Pollingintervall gemäß Skript (`scripts/e2e_probe.py`).
- Fehlerdetails sind im `detail`-Feld in Klartext enthalten.

## Wartungshinweise
- Bei neuen Phasen oder Fehlertypen Beispiele in Dokumentation aktualisieren.
- OpenAPI-Schema (`app.openapi()`) kann für API-Clients exportiert werden.
