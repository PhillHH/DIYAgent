"""Gemeinsame Report-Strukturen fuer Writer und Emailer.

Die Klassen bilden den Vertrag zwischen Writer (LLM-Ausgabe) und Emailer
(Rendering). Der Writer liefert ein `ReportPayload`-Objekt, das anschließend
fuer Markdown- und HTML-Templates genutzt wird, sodass keine Freitext-Passung
notwendig ist."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field, HttpUrl


class ReportMeta(BaseModel):
    """Meta-Informationen zu Schwierigkeitsgrad, Dauer, Kosten und Region."""

    difficulty: str = Field(default="Mittel", description="Einschaetzung des Schwierigkeitsgrads")
    duration: str = Field(default="k.A.", description="Zeitspanne inklusive Puffer")
    budget: str = Field(default="k.A.", description="Gesamter Kostenrahmen inklusive Puffer")
    region: Optional[str] = Field(default=None, description="Optionaler Regionalhinweis (z. B. DE/AT/CH)")


class ReportTOCEntry(BaseModel):
    """Inhaltsverzeichnis-Eintrag mit Titel, Anker und Gliederungsebene."""

    title: str
    anchor: str
    level: int = Field(ge=2, le=3)


class NarrativeSection(BaseModel):
    """Freitext-Sektion mit optionalen Bulletpoints und Hinweis."""

    heading: str
    paragraphs: List[str] = Field(default_factory=list)
    bullets: List[str] = Field(default_factory=list)
    note: Optional[str] = Field(default=None, description="Zusätzlicher Hinweis oder Callout")


class ShoppingItem(BaseModel):
    """Eintrag fuer die Einkaufsliste mit Bauhaus-Link."""

    position: Optional[int] = Field(default=None, description="Optionale Reihenfolge")
    category: str
    product: str
    quantity: str
    rationale: str
    price: Optional[str] = None
    url: Optional[HttpUrl] = None


class ShoppingList(BaseModel):
    """Strukturierte Einkaufsliste fuer Bauhaus-Produkte."""

    heading: str = "Einkaufsliste (Bauhaus-Links)"
    intro: Optional[str] = Field(default=None, description="Optionaler einleitender Satz")
    items: List[ShoppingItem] = Field(default_factory=list)
    empty_hint: str = "Keine geprüften Bauhaus-Produkte verfügbar."


class StepDetail(BaseModel):
    """Ein einzelner Arbeitsschritt mit Prüfkriterium und optionalen Hinweisen."""

    title: str
    bullets: List[str] = Field(default_factory=list)
    check: str = Field(description="Messbares Prüfkriterium")
    tip: Optional[str] = Field(default=None, description="Optionaler Tipp-Hinweis")
    warning: Optional[str] = Field(default=None, description="Optionaler Achtung-/Warnhinweis")


class StepsSection(BaseModel):
    """Sektion mit nummerierten Arbeitsschritten."""

    heading: str
    steps: List[StepDetail] = Field(default_factory=list)


class TimeCostRow(BaseModel):
    """Zeile der Zeit-/Kostenuebersicht."""

    work_package: str
    duration: str
    cost: str
    buffer: Optional[str] = None


class TimeCostSection(BaseModel):
    """Tabellarische Übersicht für Dauer- und Kostenplanung."""

    heading: str
    rows: List[TimeCostRow] = Field(default_factory=list)
    summary: Optional[str] = Field(default=None, description="Optionale Abschlussbewertung oder Hinweis")


class FAQItem(BaseModel):
    """Frage-Antwort-Paar der FAQ-Sektion."""

    question: str
    answer: str


class ReportPayload(BaseModel):
    """Kompletter Report-Inhalt, der in Templates gerendert wird."""

    title: str
    teaser: str
    meta: ReportMeta
    toc: List[ReportTOCEntry] = Field(default_factory=list)
    preparation: NarrativeSection
    shopping_list: ShoppingList
    step_by_step: StepsSection
    quality_safety: NarrativeSection
    time_cost: TimeCostSection
    options_upgrades: Optional[NarrativeSection] = None
    maintenance: Optional[NarrativeSection] = None
    faq: List[FAQItem] = Field(default_factory=list)
    followups: List[str] = Field(default_factory=list)
    search_summary: Optional[str] = Field(default=None, description="Optionale Recherche-Zusammenfassung")


