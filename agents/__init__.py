"""Öffentliche Agent-Schnittstellen und Modelle."""

from .emailer import send_email
from .model_settings import DEFAULT_PLANNER, DEFAULT_SEARCHER, DEFAULT_WRITER, ModelSettings
from .planner import plan_searches
from .schemas import ReportData, WebSearchItem, WebSearchPlan
from .search import perform_searches
from .writer import write_report

__all__ = [
    "DEFAULT_PLANNER",
    "DEFAULT_SEARCHER",
    "DEFAULT_WRITER",
    "ModelSettings",
    "ReportData",
    "WebSearchItem",
    "WebSearchPlan",
    "plan_searches",
    "perform_searches",
    "send_email",
    "write_report",
]

