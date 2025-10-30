"""Eingabeguard fuer Anfragen an die DIY-Pipeline."""

from __future__ import annotations

from typing import Tuple

DIY_KEYWORDS = {
    "bauen",
    "montage",
    "reparatur",
    "streichen",
    "verlegen",
    "heimwerken",
    "diy",
    "werkzeug",
    "material",
    "renovieren",
    "bohren",
}


def validate_input(raw_input: str) -> Tuple[bool, str]:
    """Trimmt und validiert eine Nutzereingabe."""

    cleaned = raw_input.strip()
    if not cleaned:
        return False, "Leere Eingabe"
    return True, cleaned


def is_diy(query: str) -> bool:
    """Prueft per Keyword-Heuristik, ob eine Anfrage DIY-Bezug besitzt."""

    lowered = query.lower()
    return any(keyword in lowered for keyword in DIY_KEYWORDS)


