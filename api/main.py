"""HTTP-Einstiegspunkt fuer orchestrierten DIY-Research."""

from __future__ import annotations

import asyncio
from uuid import uuid4

from fastapi import FastAPI
from pydantic import BaseModel

from orchestrator.pipeline import SettingsBundle, run_job
from orchestrator.status import get_status, set_status

app = FastAPI(title="Deep Research Agent API")
_SETTINGS_BUNDLE = SettingsBundle()


class StartRequest(BaseModel):
    """Request-Schema fuer den Start einer Recherche."""

    query: str
    email: str


@app.post("/start_research")
async def start_research(payload: StartRequest) -> dict[str, str]:
    """Startet einen neuen DIY-Job asynchron und liefert die Job-ID."""

    job_id = str(uuid4())
    set_status(job_id, "queued", None)
    asyncio.create_task(run_job(job_id, payload.query, payload.email, _SETTINGS_BUNDLE))
    return {"job_id": job_id}


@app.get("/status/{job_id}")
async def get_job_status(job_id: str) -> dict[str, str | None]:
    """Liefert den aktuellen Status fuer einen Job."""

    return get_status(job_id)


