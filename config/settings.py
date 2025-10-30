"""Liest Konfigurationswerte aus der .env-Datei und stellt sie zentral bereit.

Das Modul nutzt `python-dotenv`, um die Applikation durchgaengig mit identischen
Werten zu versorgen. Alle Konstanten werden beim Import berechnet."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv  # type: ignore[import]

CONFIG_DIR = Path(__file__).resolve().parent
ROOT_ENV_FILE = CONFIG_DIR.parent / ".env"
EXAMPLE_ENV_FILE = CONFIG_DIR / ".env.example"

# Prioritaet: Projektweite .env > Beispieldatei (nur als Fallback).
if ROOT_ENV_FILE.exists():
    load_dotenv(ROOT_ENV_FILE)
elif EXAMPLE_ENV_FILE.exists():
    load_dotenv(EXAMPLE_ENV_FILE)


def _as_bool(value: str, default: bool = False) -> bool:
    """Interpretation einer Umgebungsvariable als boolescher Wert."""

    if value is None:
        return default
    return str(value).lower() in {"1", "true", "yes", "on"}


# --- OpenAI / SendGrid ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", "")

# --- Tracing-Konfiguration ---
OPENAI_TRACING_ENABLED = _as_bool(
    os.getenv("OPENAI_TRACING_ENABLED", os.getenv("OPENAI_TRACE_ENABLED", "false"))
)
OPENAI_TRACE_RAW = _as_bool(os.getenv("OPENAI_TRACE_RAW", "false"))
LOG_DIR = os.getenv("LOG_DIR", "logs")
OPENAI_WEB_TOOL_TYPE = os.getenv("OPENAI_WEB_TOOL_TYPE", "web_search_preview")

# --- Planner/Search/Writer Parameter ---
HOW_MANY_SEARCHES = int(os.getenv("HOW_MANY_SEARCHES", "3"))
SEARCH_CONTEXT_SIZE = os.getenv("SEARCH_CONTEXT_SIZE", "low")

MAX_CONCURRENCY = int(os.getenv("MAX_CONCURRENCY", "5"))
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "30"))
CONCURRENCY_SEMAPHORE = MAX_CONCURRENCY
DEFAULT_TIMEOUT = REQUEST_TIMEOUT

PLANNER_MODEL_NAME = os.getenv("PLANNER_MODEL_NAME", "lab-planner-001")
SEARCH_MODEL_NAME = os.getenv("SEARCH_MODEL_NAME", "lab-search-001")
WRITER_MODEL_NAME = os.getenv("WRITER_MODEL_NAME", "lab-writer-001")
