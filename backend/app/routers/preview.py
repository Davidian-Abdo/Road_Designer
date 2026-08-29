"""GET /designs/{job_id}/preview — JSON arrays for client-side interactive
rendering (plan axis+edges, TN/projet profile, Bruckner curve).

Built entirely from the ``RoadDesign`` instance's existing public API
(``get_plan_axis``, ``get_plan_edges``, and the ``dense_pks`` /
``dense_ground_z`` / ``dense_proj_z`` / ``cubatures`` attributes populated by
``RoadDesign.__init__`` — see CLAUDE.md § 5 road_design.py). No new engine
computation is added; this router only serialises arrays that already exist,
made available via ``build_design(..., return_design=True)`` (the one
additive engine hook, CLAUDE.md § "Three-surface architecture").
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .. import jobs

router = APIRouter(tags=["preview"])


@router.get("/designs/{job_id}/preview")
def get_preview(job_id: str):
    job = jobs.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Unknown or expired job_id.")
    if job.status != "done" or job.design is None:
        raise HTTPException(status_code=409, detail=f"Job is '{job.status}', not done yet.")

    design = job.design

    axis = design.get_plan_axis()
    edges_left, edges_right = design.get_plan_edges()

    plan = {
        "axis": axis.tolist(),
        "edges_left": edges_left.tolist(),
        "edges_right": edges_right.tolist(),
    }
    profile = {
        "pk": design.dense_pks.tolist(),
        "tn": design.dense_ground_z.tolist(),
        "projet": design.dense_proj_z.tolist(),
    }
    bruckner = {
        "pk": design.vert_pks.tolist(),
        "m": (design.cubatures.bruckner.tolist() if design.cubatures is not None else []),
    }

    return {"plan": plan, "profile": profile, "bruckner": bruckner}
