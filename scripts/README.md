# Scripts

## Schnellzugriff
- [Projekt-Docs-Index](../README.md#dokumentation--navigation)
- [API README](../api/README.md) – Endpunkte & Statusformat
- [E2E-Probe Quellcode](e2e_probe.py)

## Zweck
- `e2e_probe.py` fuehrt eine End-to-End-Probe gegen die laufende FastAPI durch.
- `dev.ps1` / `dev.sh` starten uvicorn im Projekt-Venv (inkl. `--reload`).
- Ideal fuer manuelle Funktionstests und CI-Sanity-Checks.

## Schnittstellen / Vertraege
- `e2e_probe.py`: CLI-Parameter `--email` (Pflicht), optional `--query`, `--base-url` (Default `http://localhost:8005`), `--interval`, `--timeout`.
- `dev.ps1` (PowerShell): optional `-ListenHost`, `-Port` (Default 8005).
- `dev.sh` (POSIX): nutzt Umgebungsvariablen `HOST` und `PORT` (Defaults `127.0.0.1:8005`).
- Exit-Code `0` bei Erfolg, `1` bei Fehler oder Timeout.

## Beispielablauf
```powershell
./scripts/dev.ps1 -ListenHost 127.0.0.1 -Port 8005
# In zweitem Terminal
python scripts/e2e_probe.py --email user@example.com --base-url http://127.0.0.1:8005
```
- Skript startet Job, pollt `/status/{job_id}` alle 2 s, zeigt Phasen in der Konsole an.

## Grenzen & Annahmen
- `e2e_probe.py` benötigt laufenden Uvicorn-Server (z. B. via `dev.ps1`/`dev.sh`).
- Skripte lesen `.env` im Projektstamm; Shell-Variablen überschreiben Werte.
- Keine automatische Wiederholung bei Fehlern – manuell erneut starten.

## Wartungshinweise
- Bei API-Aenderungen Parameter aktualisieren.
- Exit-Codes und Fehlermeldungen stabil halten, damit CI-Skripte darauf reagieren können.
- `dev.ps1` vermeidet Konflikte mit PowerShells `$Host`-Variable (verwendet `-ListenHost`).
