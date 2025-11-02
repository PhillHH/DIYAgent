"""Pydantic-Schemas fuer Planungs- und Report-Outputs."""

from __future__ import annotations

from pydantic import BaseModel, Field

from models.types import ProductItem


class WebSearchItem(BaseModel):
    """Einzelne Suchaufgabe mit Grund und Query."""

    reason: str = Field(..., description="Warum diese Suche")
    query: str = Field(..., description="Suchbegriff")


class WebSearchPlan(BaseModel):
    """Sammlung aller geplanten Suchaufgaben."""

    searches: list[WebSearchItem] = Field(..., min_length=1)


class ReportData(BaseModel):
    """Strukturiertes Endergebnis fuer den DIY-Report."""

    short_summary: str
    markdown_report: str
    followup_questions: list[str] = Field(default_factory=list)


