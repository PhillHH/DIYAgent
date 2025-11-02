"""CLI-Skript fuer End-to-End-Proben der DIY-Pipeline.

Das Skript startet Jobs ueber die FastAPI, pollt ihren Status und liefert einen
passenden Exit-Code – ideal fuer manuelle Smoke-Tests oder CI-Pruefungen."""

from __future__ import annotations

import argparse
import os
import sys
import time
from typing import Dict, Iterable, Optional

import httpx
from dotenv import load_dotenv

REQUIRED_ENV_VARS = ["OPENAI_API_KEY", "SENDGRID_API_KEY", "FROM_EMAIL"]


# Umgebung aus .env einlesen, damit lokale Proben ohne manuelles Exportieren laufen.
load_dotenv()


def ensure_environment() -> None:
    """Validiert, dass alle benoetigten Umgebungsvariablen vorhanden sind."""

    missing = [name for name in REQUIRED_ENV_VARS if not os.getenv(name)]
    if missing:
        names = ", ".join(missing)
        raise RuntimeError(
            f"Fehlende Umgebungsvariablen: {names}. Bitte .env aktualisieren und erneut versuchen."
        )


def trigger_job(client: httpx.Client, base_url: str, query: str, email: str) -> str:
    """Startet einen neuen Recherchejob und liefert dessen ID."""

    response = client.post(f"{base_url}/start_research", json={"query": query, "email": email})
    response.raise_for_status()
    payload = response.json()
    job_id = payload.get("job_id")
    if not job_id:
        raise RuntimeError("Antwort enthaelt keine job_id. Bitte Server-Logs pruefen.")
    return str(job_id)


def poll_status(
    client: httpx.Client,
    base_url: str,
    job_id: str,
    interval: float,
    timeout: float,
) -> Dict[str, object]:
    """Fragt den Status zyklisch ab, bis ein Endzustand erreicht ist."""

    start = time.monotonic()
    seen_phases: set[str] = set()

    while True:
        response = client.get(f"{base_url}/status/{job_id}")
        response.raise_for_status()
        status = response.json()
        phase = status.get("phase", "unknown")
        detail = status.get("detail")

        if phase not in seen_phases:
            print(f"Phase '{phase}' erreicht." + (f" Detail: {detail}" if detail else ""))
            seen_phases.add(phase)

        if phase in {"done", "rejected", "error"}:
            return status

        if time.monotonic() - start > timeout:
            raise TimeoutError("Timeout: Pipeline brauchte zu lange.")

        time.sleep(interval)


def run_probe(
    base_url: str,
    query: str,
    email: str,
    interval: float,
    timeout: float,
) -> int:
    """Fuehrt die komplette Probe aus und gibt den Exit-Code zurueck."""

    ensure_environment()

    print(f"Starte E2E-Probe fuer Anfrage: {query}")
    with httpx.Client(timeout=30) as client:
        job_id = trigger_job(client, base_url, query, email)
        print(f"Job gestartet mit ID: {job_id}")
        status = poll_status(client, base_url, job_id, interval, timeout)

    phase = status.get("phase", "unknown")
    detail = status.get("detail")
    print(f"Finaler Status: {phase}" + (f" ({detail})" if detail else ""))
    if phase == "done":
        payload = status.get("payload") or {}
        if isinstance(payload, dict):
            links = payload.get("email_links") or []
        else:
            links = []
        bauhaus_links = [
            link
            for link in links
            if isinstance(link, str) and "bauhaus" in link.lower()
        ]
        if not bauhaus_links:
            print("Warnung: Keine Bauhaus-Links im finalen HTML gefunden.")
            return 1
    return 0 if phase == "done" else 1


def build_arg_parser() -> argparse.ArgumentParser:
    """Erzeugt den CLI-Argumentparser."""

    parser = argparse.ArgumentParser(description="End-to-End-Probe fuer die Home-Task-AI-Pipeline")
    parser.add_argument("--base-url", default="http://127.0.0.1:8005", help="Basis-URL der API")
    parser.add_argument(
        "--query",
        default="Laminat in 20 qm verlegen - Arbeitsschritte und Materialliste",
        help="Forschungsfrage fuer die Probe",
    )
    parser.add_argument("--email", required=True, help="Empfaengeradresse fuer den Report")
    parser.add_argument("--interval", type=float, default=2.0, help="Polling-Intervall in Sekunden")
    parser.add_argument("--timeout", type=float, default=300.0, help="Timeout in Sekunden")
    return parser


def main(argv: Optional[Iterable[str]] = None) -> int:
    """CLI-Einstiegspunkt fuer das Skript."""

    parser = build_arg_parser()
    args = parser.parse_args(argv)

    try:
        return run_probe(args.base_url, args.query, args.email, args.interval, args.timeout)
    except TimeoutError as error:
        print(str(error))
        return 1
    except Exception as error:
        print(f"Fehler bei der Probe: {error}")
        return 1


if __name__ == "__main__":  # pragma: no cover - manueller Aufruf
    sys.exit(main())

