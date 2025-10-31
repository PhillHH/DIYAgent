# Scripts

## Zweck
- `e2e_probe.py` fuehrt eine End-to-End-Probe gegen die laufende FastAPI durch.
- `dev.ps1` / `dev.sh` starten uvicorn im Projekt-Venv (inkl. `--reload`).
- Ideal fuer manuelle Funktionstests und CI-Sanity-Checks.

## Schnittstellen / Vertraege
- `e2e_probe.py`: CLI-Parameter `--email` (Pflicht), optional `--query`, `--base-url`, `--interval`, `--timeout`.
- `dev.ps1` (PowerShell): optional `-ListenHost`, `-Port`.
- Exit-Code `0` bei Erfolg, `1` bei Fehler oder Timeout.

## Beispielablauf
```powershell
./scripts/dev.ps1
# In zweitem Terminal
python scripts/e2e_probe.py --email user@example.com
```
- Skript startet Job, pollt Status alle 2s, zeigt Phasen in der Konsole an.

## Grenzen & Annahmen
- `e2e_probe.py` benötigt laufenden Uvicorn-Server (z. B. via `dev.ps1`/`dev.sh`).
- Skripte lesen `.env` im Projektstamm; Shell-Variablen überschreiben Werte.
- Keine automatische Wiederholung bei Fehlern – manuell erneut starten.

## Wartungshinweise
- Bei API-Aenderungen Parameter aktualisieren.
- Exit-Codes und Fehlermeldungen stabil halten, damit CI-Skripte darauf reagieren können.
