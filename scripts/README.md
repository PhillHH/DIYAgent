# Scripts

## Zweck
- `e2e_probe.py` fuehrt eine End-to-End-Probe gegen die laufende FastAPI durch.
- Ideal fuer manuelle Funktionstests und CI-Sanity-Checks.

## Schnittstellen / Vertraege
- CLI-Parameter: `--email` (Pflicht), optional `--query`, `--base-url`, `--interval`, `--timeout`.
- Exit-Code `0` bei Erfolg, `1` bei Fehler oder Timeout.

## Beispielablauf
```powershell
python scripts/e2e_probe.py --email user@example.com
```
- Skript startet Job, pollt Status alle 2s, zeigt Phasen in der Konsole an.

## Grenzen & Annahmen
- Benötigt laufenden Uvicorn-Server (`uvicorn api.main:app --reload`).
- Verwendet `.env` im Projektstamm; Shell-Variablen überschreiben Werte.
- Keine automatische Wiederholung bei Fehlern – manuell erneut starten.

## Wartungshinweise
- Bei API-Aenderungen Parameter aktualisieren.
- Exit-Codes und Fehlermeldungen stabil halten, damit CI-Skripte darauf reagieren können.
