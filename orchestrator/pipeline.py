"""Asynchrone Orchestrierung des Home-Task-AI-Flows."""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
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
from agents.search import perform_searches, perform_product_enrichment
from agents.writer import write_report
from guards.llm_input_guard import classify_query_llm
from guards.llm_output_guard import audit_report_llm
from orchestrator.status import set_status
from models.types import ProductItem

_LOGGER = logging.getLogger(__name__)

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
    job_context: dict[str, object] = {}

    try:
        set_status(job_id, "planning", None)

        guard_result = await classify_query_llm(query, bundle.guard)
        if guard_result.category == "REJECT":
            set_status(job_id, "rejected", "Kein zulässiger Scope: " + "; ".join(guard_result.reasons))
            return

        set_status(job_id, "planning", "Kategorie: " + guard_result.category)

        plan = await plan_searches(query, bundle.planner)

        set_status(job_id, "searching", None)
        summaries, _ = await perform_searches(
            plan,
            bundle.searcher,
            user_query=query,
            category=guard_result.category,
        )
        product_results: list[ProductItem] = []
        is_diy = (guard_result.category or "").upper() == "DIY"
        if is_diy:
            product_results = await perform_product_enrichment(
                query,
                summaries,
                bundle.searcher,
            )
        if product_results:
            _LOGGER.info(
                "SEARCH products: %d %s",
                len(product_results),
                [item.url for item in product_results[:2]],
            )
        else:
            _LOGGER.warning("SEARCH products: keine Produkte extrahiert")
        job_context["product_results"] = [item.model_dump() for item in product_results]

        set_status(job_id, "writing", None)
        report = await write_report(
            query,
            summaries,
            bundle.writer,
            category=guard_result.category,
            product_results=product_results,
        )

        if report.payload is not None:
            job_context["report_payload"] = report.payload.model_dump()

        audit = await audit_report_llm(query, report.markdown_report, bundle.guard)
        if not audit.allowed:
            set_status(job_id, "rejected", "Policy: " + "; ".join(audit.issues))
            return

        set_status(job_id, "email", None)
        email_result = await send_email(
            report,
            to_email,
            product_results=product_results,
        )

        bauhaus_links = [
            link
            for link in email_result.get("links", [])
            if isinstance(link, str) and "bauhaus" in link.lower()
        ]
        payload = {
            "email_links": list(bauhaus_links),
            "email_preview": email_result.get("html_preview"),
            "product_results": job_context.get("product_results"),
            "report_payload": job_context.get("report_payload"),
        }

        set_status(job_id, "done", None, payload=payload)
    except Exception as error:  # pragma: no cover - Fehlerszenarien in Produktion loggen
        set_status(job_id, "error", str(error))


