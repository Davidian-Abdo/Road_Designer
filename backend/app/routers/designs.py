"""POST /designs, GET /designs/{id}, GET /designs/{id}/files/{kind}.

Wraps ``road_designer.road_design.build_design()`` — no engine logic here.
"""
from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import ValidationError

from .. import jobs
from ..schemas import DesignConfigIn, JobCreated, JobFiles, JobStatus

router = APIRouter(tags=["designs"])

_FILE_KIND_META = {
    "dxf": "application/dxf",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pdf_plan": "application/pdf",
    "pdf_pt": "application/pdf",
}


@router.post("/designs", response_model=JobCreated, status_code=202)
async def create_design(
    axe: UploadFile = File(..., description="Axe en plan (.txt)"),
    terrain: Optional[UploadFile] = File(
        None, description="Terrain CSV (X,Y,Z). Omit to use synth_terrain params."
    ),
    config: str = Form(..., description="JSON-encoded DesignConfigIn"),
):
    try:
        cfg_in = DesignConfigIn.model_validate_json(config)
    except ValidationError as exc:
        # exc.errors() includes a raw exception object under ctx["error"] for
        # value_error entries (e.g. our company_name validator) — not JSON
        # serializable, so only forward the plain-data fields.
        errors = [
            {"type": e["type"], "loc": e["loc"], "msg": e["msg"]}
            for e in exc.errors()
        ]
        raise HTTPException(status_code=422, detail=errors) from exc

    if terrain is None and cfg_in.synth_terrain is None:
        raise HTTPException(
            status_code=422,
            detail="Provide either a terrain CSV file or config.synth_terrain params.",
        )

    axe_bytes = await axe.read()
    terrain_bytes = await terrain.read() if terrain is not None else None
    synth_kwargs = (
        cfg_in.synth_terrain.model_dump() if cfg_in.synth_terrain is not None else None
    )

    cfg = cfg_in.to_design_config()
    job = jobs.create_job(cfg, axe_bytes, terrain_bytes, synth_kwargs)

    # Fire-and-forget: the request returns 202 immediately: the client polls
    # GET /designs/{id}. No external broker — a small asyncio task backed by
    # a ThreadPoolExecutor (see jobs.py) does the actual (CPU-bound) work.
    asyncio.create_task(jobs.submit(job))

    return JobCreated(job_id=job.id, status="queued")


@router.get("/designs/{job_id}", response_model=JobStatus)
def get_design(job_id: str):
    job = jobs.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Unknown or expired job_id.")

    files = None
    if job.files is not None:
        files = JobFiles(**{
            kind: f"/designs/{job_id}/files/{kind}" for kind in job.files
        })

    return JobStatus(
        job_id=job.id,
        status=job.status,
        files=files,
        warnings=job.warnings,
        error=job.error,
    )


@router.get("/designs/{job_id}/files/{kind}")
def get_design_file(job_id: str, kind: str):
    if kind not in _FILE_KIND_META:
        raise HTTPException(status_code=404, detail=f"Unknown file kind '{kind}'.")

    job = jobs.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Unknown or expired job_id.")
    if job.status != "done" or job.files is None:
        raise HTTPException(status_code=409, detail=f"Job is '{job.status}', not done yet.")

    path = job.files[kind]
    return FileResponse(path, media_type=_FILE_KIND_META[kind], filename=path.name)
