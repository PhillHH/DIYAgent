"""Pydantic-Schemas fuer Planungs- und Report-Outputs."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, field_validator

from models.report_payload import ReportPayload

from models.types import ProductItem


class SearchPhase(str, Enum):
    """Feste Menge erlaubter Recherche-Phasen."""

    VORBEREITUNG_PLANUNG = "Vorbereitung & Planung"
    MATERIAL_WERKZEUGE = "Material & Werkzeuge"
    SICHERHEIT_UMWELT = "Sicherheit & Umwelt"
    DEMONTAGE_UNTERGRUND = "Demontage/Untergrund"
    AUSFUEHRUNG = "Schritt-für-Schritt-Ausführung"
    QUALITAET_KONTROLLE = "Qualität & Kontrolle"
    ZEIT_KOSTEN = "Zeit & Kosten"
    OPTIONEN_UPGRADES = "Optionen & Upgrades"
    PFLEGE_WARTUNG = "Pflege & Wartung"
    VISUAL_GUIDE = "Visual Guide"


class WebSearchItem(BaseModel):
    """Einzelne Suchaufgabe mit Grund und Query."""

    reason: SearchPhase = Field(..., description="Warum diese Suche")
    query: str = Field(..., description="Suchbegriff")


class WebSearchPlan(BaseModel):
    """Sammlung aller geplanten Suchaufgaben."""

    searches: list[WebSearchItem] = Field(..., min_length=1, max_length=10)

    @field_validator("searches")
    @classmethod
    def _validate_unique_reason(cls, value: list[WebSearchItem]) -> list[WebSearchItem]:
        reasons = [item.reason for item in value]
        if len(set(reasons)) != len(reasons):
            raise ValueError("reason must be unique per search list")
        return value


class ReportData(BaseModel):
    """Strukturiertes Endergebnis fuer den DIY-Report."""

    short_summary: str
    markdown_report: str
    followup_questions: list[str] = Field(default_factory=list)
    payload: ReportPayload | None = Field(
        default=None,
        description="Strukturierter Report zur Wiederverwendung in Templates",
    )


