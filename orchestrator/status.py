"""Einfacher In-Memory-Statusspeicher fuer Pipeline-Jobs."""

from __future__ import annotations

from threading import Lock
from typing import Dict, Optional

_STATUSES: Dict[str, Dict[str, Optional[str]]] = {}
_LOCK = Lock()


def set_status(job_id: str, phase: str, detail: Optional[str] = None) -> None:
    """Speichert den aktuellen Phase-Detail-Status fuer einen Job."""

    with _LOCK:
        _STATUSES[job_id] = {
            "job_id": job_id,
            "phase": phase,
            "detail": detail,
        }


def get_status(job_id: str) -> Dict[str, Optional[str]]:
    """Liefert den zuletzt bekannten Status oder einen Platzhalter."""

    with _LOCK:
        return _STATUSES.get(
            job_id,
            {
                "job_id": job_id,
                "phase": "unknown",
                "detail": "Job wurde nicht gefunden",
            },
        )


def reset_statuses() -> None:
    """Loescht saemtliche gespeicherten Statusinformationen (Test-Utility)."""

    with _LOCK:
        _STATUSES.clear()


