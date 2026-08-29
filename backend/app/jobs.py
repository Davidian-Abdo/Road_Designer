"""In-memory job store + background runner for design builds.

No external broker (no Redis/Celery) — a small ``ThreadPoolExecutor`` runs
``road_designer.road_design.build_design()`` off the asyncio event loop
(SLSQP + matplotlib PDF rendering are CPU-bound and can take tens of
seconds), while the job dict tracks status for polling clients.

Jobs are NOT expected to survive a process restart — HF Spaces free tier can
recycle the container, and that's fine per the task spec. A periodic sweep
evicts jobs (and deletes their tempdir) after ``JOB_TTL_SECONDS``.
"""
from __future__ import annotations

import asyncio
import shutil
import tempfile
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from road_designer.config import DesignConfig
from road_designer.road_design import build_design

JOB_TTL_SECONDS = 30 * 60
SWEEP_INTERVAL_SECONDS = 5 * 60

JobStatusLiteral = str  # "queued" | "running" | "done" | "error"


@dataclass
class Job:
    id: str
    cfg: DesignConfig
    tmpdir: Path
    axe_path: Path
    terrain_path: Path
    status: JobStatusLiteral = "queued"
    created_at: float = field(default_factory=time.time)
    files: Optional[Dict[str, Path]] = None
    warnings: Optional[List[str]] = None
    error: Optional[str] = None
    design: Optional[object] = None  # RoadDesign, for the preview endpoint


JOBS: Dict[str, Job] = {}
_executor = ThreadPoolExecutor(max_workers=2)


def _run_build(job: Job) -> None:
    job.status = "running"
    try:
        result = build_design(
            job.cfg, job.axe_path, job.terrain_path,
            job.tmpdir / "out", return_design=True,
        )
        job.files = {
            "dxf": result["dxf"],
            "xlsx": result["xlsx"],
            "pdf_plan": result["pdf_plan"],
            "pdf_pt": result["pdf_pt"],
        }
        job.warnings = list(result["warnings"])
        job.design = result["design"]
        job.status = "done"
    except Exception as exc:  # noqa: BLE001 — surfaced to the client as job.error
        job.error = str(exc)
        job.status = "error"


def create_job(
    cfg: DesignConfig,
    axe_bytes: bytes,
    terrain_bytes: Optional[bytes] = None,
    synth_terrain_kwargs: Optional[dict] = None,
) -> Job:
    """Create a job, resolving the terrain either from an uploaded CSV or
    from synthetic-terrain params (mirrors the Streamlit "Générer
    synthétique" mode in ``frontends/streamlit/app.py``)."""
    tmpdir = Path(tempfile.mkdtemp(prefix="road_designer_api_"))
    axe_path = tmpdir / "axe.txt"
    terrain_path = tmpdir / "terrain.csv"
    axe_path.write_bytes(axe_bytes)

    if terrain_bytes is not None:
        terrain_path.write_bytes(terrain_bytes)
    else:
        from road_designer.samples_api import generate_synthetic_terrain
        generate_synthetic_terrain(axe_path, terrain_path, **(synth_terrain_kwargs or {}))

    job = Job(
        id=str(uuid.uuid4()),
        cfg=cfg,
        tmpdir=tmpdir,
        axe_path=axe_path,
        terrain_path=terrain_path,
    )
    JOBS[job.id] = job
    return job


async def submit(job: Job) -> None:
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(_executor, _run_build, job)


def get_job(job_id: str) -> Optional[Job]:
    return JOBS.get(job_id)


def _evict(job_id: str) -> None:
    job = JOBS.pop(job_id, None)
    if job is not None:
        shutil.rmtree(job.tmpdir, ignore_errors=True)


async def sweep_loop() -> None:
    """Background task: evict jobs older than JOB_TTL_SECONDS every 5 min."""
    while True:
        await asyncio.sleep(SWEEP_INTERVAL_SECONDS)
        now = time.time()
        expired = [
            jid for jid, job in JOBS.items()
            if now - job.created_at > JOB_TTL_SECONDS
        ]
        for jid in expired:
            _evict(jid)
