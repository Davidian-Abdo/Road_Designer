"""End-to-end coverage of the /designs API: submit -> poll -> done, file
download, validation error on missing company_name, preview payload shape.

The full build (SLSQP + DXF/XLSX/PDF rendering) is expensive, so a single
job is built once per session (``done_job`` fixture) and reused across the
assertions below — same pattern as the engine suite's session-scoped
``design`` fixture in tests/conftest.py.
"""
from __future__ import annotations

import json
import time

import pytest


def _wait_until_finished(client, job_id: str, timeout: float = 240.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        body = client.get(f"/designs/{job_id}").json()
        if body["status"] in ("done", "error"):
            return body
        time.sleep(1.0)
    raise TimeoutError(f"job {job_id} did not finish within {timeout}s")


@pytest.fixture(scope="session")
def done_job(client, axe_path, terrain_path, valid_config_json) -> str:
    with open(axe_path, "rb") as af, open(terrain_path, "rb") as tf:
        resp = client.post(
            "/designs",
            files={
                "axe": ("sample_axe.txt", af, "text/plain"),
                "terrain": ("sample_terrain.csv", tf, "text/csv"),
            },
            data={"config": valid_config_json},
        )
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["status"] == "queued"
    job_id = body["job_id"]

    final = _wait_until_finished(client, job_id)
    assert final["status"] == "done", final
    return job_id


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_missing_company_name_is_rejected(client, axe_path, terrain_path):
    bad_config = json.dumps({
        "road_category": "CAT_1",
        "cartouche": {"company_name": "   "},
    })
    with open(axe_path, "rb") as af, open(terrain_path, "rb") as tf:
        resp = client.post(
            "/designs",
            files={"axe": ("a.txt", af, "text/plain"), "terrain": ("t.csv", tf, "text/csv")},
            data={"config": bad_config},
        )
    assert resp.status_code == 422


def test_no_terrain_and_no_synth_params_is_rejected(client, axe_path, valid_config_json):
    with open(axe_path, "rb") as af:
        resp = client.post(
            "/designs",
            files={"axe": ("a.txt", af, "text/plain")},
            data={"config": valid_config_json},
        )
    assert resp.status_code == 422


def test_unknown_job_id_404s(client):
    assert client.get("/designs/does-not-exist").status_code == 404
    assert client.get("/designs/does-not-exist/files/dxf").status_code == 404
    assert client.get("/designs/does-not-exist/preview").status_code == 404


def test_job_lifecycle_and_file_downloads(client, done_job):
    status = client.get(f"/designs/{done_job}").json()
    assert status["status"] == "done"
    assert status["files"] is not None
    assert status["error"] is None

    for kind, content_type_prefix in (
        ("dxf", None),
        ("xlsx", "application/vnd"),
        ("pdf_plan", "application/pdf"),
        ("pdf_pt", "application/pdf"),
    ):
        url = status["files"][kind]
        resp = client.get(url)
        assert resp.status_code == 200, (kind, resp.text)
        assert len(resp.content) > 0
        if content_type_prefix:
            assert resp.headers["content-type"].startswith(content_type_prefix)


def test_unknown_file_kind_404s(client, done_job):
    assert client.get(f"/designs/{done_job}/files/nope").status_code == 404


def test_preview_payload_shape(client, done_job):
    resp = client.get(f"/designs/{done_job}/preview")
    assert resp.status_code == 200
    body = resp.json()

    assert set(body.keys()) == {"plan", "profile", "bruckner"}

    plan = body["plan"]
    assert set(plan.keys()) == {"axis", "edges_left", "edges_right"}
    assert len(plan["axis"]) > 0
    assert all(len(pt) == 2 for pt in plan["axis"][:5])

    profile = body["profile"]
    assert len(profile["pk"]) == len(profile["tn"]) == len(profile["projet"])
    assert len(profile["pk"]) > 0

    bruckner = body["bruckner"]
    assert len(bruckner["pk"]) == len(bruckner["m"])
    assert len(bruckner["pk"]) > 0
