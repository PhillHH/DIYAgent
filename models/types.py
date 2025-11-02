"""Gemeinsame Pydantic-Typen fuer strukturierte Daten."""

from __future__ import annotations

from pydantic import BaseModel, HttpUrl


class ProductItem(BaseModel):
    """Strukturiertes Produkt aus der Bauhaus-Suche."""

    title: str
    url: HttpUrl
    note: str | None = None
    price_text: str | None = None


__all__ = ["ProductItem"]

