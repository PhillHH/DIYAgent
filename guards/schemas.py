"""Pydantic-Schemas fuer Guard-Routinen."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class InputGuardResult(BaseModel):
    """LLM-basierte Klassifikation einer Anfrage."""

    category: Literal["DIY", "KI_CONTROL", "REJECT"]
    reasons: list[str]


class OutputGuardResult(BaseModel):
    """Resultat der LLM-Ausgabenkontrolle."""

    allowed: bool
    issues: list[str] = Field(default_factory=list)
    category: Literal["DIY", "KI_CONTROL", "UNKNOWN"] = "UNKNOWN"
