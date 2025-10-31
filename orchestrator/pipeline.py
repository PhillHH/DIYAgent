"""Asynchrone Orchestrierung des DIY-Research-Flows."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from agents.emailer import send_email
from agents.model_settings import (
    DEFAULT_GUARD,
    DEFAULT_PLANNER,
    DEFAULT_SEARCHER,
    DEFAULT_WRITER,
    ModelSettings,
)
from agents.planner import plan_searches
from agents.search import perform_searches
from agents.writer import write_report
from guards.llm_input_guard import classify_query_llm
from guards.llm_output_guard import audit_report_llm
from orchestrator.status import set_status


@dataclass
class SettingsBundle:
    """Bündelt Modellkonfigurationen fuer alle Agenten."""

    planner: ModelSettings = field(default_factory=lambda: DEFAULT_PLANNER.model_copy())
    searcher: ModelSettings = field(default_factory=lambda: DEFAULT_SEARCHER.model_copy())
    writer: ModelSettings = field(default_factory=lambda: DEFAULT_WRITER.model_copy())
    guard: ModelSettings = field(default_factory=lambda: DEFAULT_GUARD.model_copy())


async def run_job(
    job_id: str,
    query: str,
    to_email: str,
    settings_bundle: Optional[SettingsBundle] = None,
) -> None:
    """Steuert den kompletten DIY-Prozess von Planung bis Versand.

    Args:
        job_id: Eindeutige Kennung fuer den laufenden Job.
        query: Nutzerfrage.
        to_email: Empfaengeradresse fuer den finalen Report.
        settings_bundle: Optional angepasste Modellkonfigurationen.

    Side Effects:
        Aktualisiert den Status-Store und versendet bei Erfolg eine E-Mail.
    """

    bundle = settings_bundle or SettingsBundle()

    try:
        set_status(job_id, "planning", None)

        guard_result = await classify_query_llm(query, bundle.guard)
        if guard_result.category == "REJECT":
            set_status(job_id, "rejected", "Kein zulässiger Scope: " + "; ".join(guard_result.reasons))
            return

        set_status(job_id, "planning", "Kategorie: " + guard_result.category)

        plan = await plan_searches(query, bundle.planner)

        set_status(job_id, "searching", None)
        summaries = await perform_searches(plan, bundle.searcher)

        set_status(job_id, "writing", None)
        report = await write_report(query, summaries, bundle.writer, category=guard_result.category)

        audit = await audit_report_llm(query, report.markdown_report, bundle.guard)
        if not audit.allowed:
            set_status(job_id, "rejected", "Policy: " + "; ".join(audit.issues))
            return

        set_status(job_id, "email", None)
        await send_email(report, to_email)

        set_status(job_id, "done", None)
    except Exception as error:  # pragma: no cover - Fehlerszenarien in Produktion loggen
        set_status(job_id, "error", str(error))


