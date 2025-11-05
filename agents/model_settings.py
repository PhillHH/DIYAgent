"""Modul zur Verwaltung der Modellkonfigurationen fuer alle KI-Agenten.

Das Modul definiert strukturierte Einstellungen fuer OpenAI-Aufrufe und stellt
praxeiserprobte Defaults fuer Planner, Searcher und Writer bereit. Durch die
Bündelung an zentraler Stelle lassen sich spätere Modellwechsel konsistent durchführen."""

from __future__ import annotations

from pydantic import BaseModel

from config import (
    GUARD_MODEL,
    GUARD_TEMPERATURE,
    PLANNER_MODEL_NAME,
    SEARCH_MODEL_NAME,
    WRITER_MODEL_NAME,
)


class ModelSettings(BaseModel):
    """Kapselt die Parameter fuer einen OpenAI-Aufruf.

    Attributes:
        model: Name des zu verwendenden OpenAI-Modells.
        temperature: Kreativitaet des Modells (0 = deterministisch).
        max_tokens: Optionales Limit fuer die Antwortlaenge in Tokens.

    Methods:
        to_openai_kwargs: Ueberfuehrt die Instanzwerte in ein kompatibles Keyword-Dict.
    """

    model: str
    temperature: float = 0.2
    max_tokens: int | None = None

    def to_openai_kwargs(self) -> dict[str, object]:
        """Liefert Standardargumente fuer `client.responses.create`.

        Returns:
            Dictionary mit Modell, Temperatur und optionalem Token-Limit.
        """

        kwargs: dict[str, object] = {
            "model": self.model,
            "temperature": self.temperature,
        }
        if self.max_tokens is not None:
            kwargs["max_output_tokens"] = self.max_tokens
        return kwargs


# Voreinstellungen, die eine ausbalancierte Mischung aus Kosten und Qualitaet bieten.
DEFAULT_PLANNER = ModelSettings(model=PLANNER_MODEL_NAME, temperature=0.1, max_tokens=1_000)
DEFAULT_SEARCHER = ModelSettings(model=SEARCH_MODEL_NAME, temperature=0.3, max_tokens=900)
DEFAULT_WRITER = ModelSettings(model=WRITER_MODEL_NAME, temperature=0.2, max_tokens=4_000)
DEFAULT_GUARD = ModelSettings(model=GUARD_MODEL, temperature=GUARD_TEMPERATURE, max_tokens=None)

