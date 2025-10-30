"""Ausgabeguard fuer DIY-Reports."""

from __future__ import annotations

from typing import Tuple

DIY_KEYWORDS = {
    "diy",
    "bauen",
    "werkzeug",
    "anleitung",
    "heimwerken",
    "holz",
    "lack",
    "material",
    "schraube",
    "farbe",
    "bohren",
    "saegen",
    "schleifen",
    "wand",
    "boden",
    "renovieren",
    "streichen",
    "laminat",
    "parkett",
    "bodenbelag",
    "verlegen",
    "montage",
    "installation",
}

NON_DIY_KEYWORDS = {
    "aktie",
    "krypto",
    "finanz",
    "derivat",
    "marketing",
    "reise",
    "medizin",
    "pharma",
    "recht",
}


def audit_output(generated_text: str) -> Tuple[bool, str]:
    """Validiert generierte Inhalte und gibt diese ggf. zurueck."""

    if not validate_report(generated_text):
        return False, "Der Inhalt wirkt nicht wie ein Heimwerker-Ergebnis"
    return True, generated_text


def validate_report(md: str) -> bool:
    """Prueft einen Markdown-Text auf Heimwerkerbezug."""

    text = (md or "").lower()
    if not text.strip():
        return False

    if any(token in text for token in NON_DIY_KEYWORDS):
        return False

    return any(token in text for token in DIY_KEYWORDS)


