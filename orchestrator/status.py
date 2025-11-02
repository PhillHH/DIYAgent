"""Einfacher In-Memory-Statusspeicher fuer Pipeline-Jobs."""

from __future__ import annotations

from threading import Lock
from typing import Any, Dict, Optional

_STATUSES: Dict[str, Dict[str, Any]] = {}
_LOCK = Lock()


def set_status(
    job_id: str,
    phase: str,
    detail: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> None:
    """Speichert den aktuellen Status sowie optionale Zusatzinformationen.

    Args:
        job_id: Eindeutige Kennung.
        phase: Aktuelle Phase (`queued`, `planning`, …, `done`).
        detail: Freitext, z. B. Fehlermeldung oder Kategorie.
        payload: Optionale Zusatzdaten (z. B. Links, HTML-Vorschau).
    """

    with _LOCK:
        _STATUSES[job_id] = {
            "job_id": job_id,
            "phase": phase,
            "detail": detail,
            "payload": payload,
        }


def get_status(job_id: str) -> Dict[str, Any]:
    """Liefert den zuletzt bekannten Status oder einen Platzhalter."""

    with _LOCK:
        return _STATUSES.get(
            job_id,
            {
                "job_id": job_id,
                "phase": "unknown",
                "detail": "Job wurde nicht gefunden",
                "payload": None,
            },
        )


def reset_statuses() -> None:
    """Loescht saemtliche gespeicherten Statusinformationen (Test-Utility)."""

    with _LOCK:
        _STATUSES.clear()


