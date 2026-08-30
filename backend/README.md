# Road Designer — FastAPI backend

The API layer for the React frontend (`frontends/react/`). Wraps the same
`road_designer.road_design.build_design()` entry point the CLI and Streamlit app use — no
engine logic lives here, only request handling, job tracking, and file streaming.

See the repo root `CLAUDE.md` § 15 ("Deployment architecture — three surfaces") for how this
fits with the other two surfaces, and § 6 for the `DesignConfig` contract this API mirrors.

## Local development

From the **repo root** (not from inside `backend/`) so `road_designer` resolves on the path:

```bash
python -m venv .venv                 # or reuse an existing venv with the root requirements installed
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --reload
```

Serves on `http://localhost:8000` by default. `ALLOWED_ORIGIN` defaults to `"*"` when unset —
fine for local dev, but **must** be set to the real Cloudflare Pages origin before/at first
production deploy (see the env var table below).

Interactive API docs: `http://localhost:8000/docs` (FastAPI's built-in Swagger UI).

## Running tests

```bash
pip install -r backend/requirements.txt   # includes pytest + httpx
pytest backend/tests/ -q
```

`backend/tests/conftest.py` reuses the repo-root `tests/conftest.py`'s `axe_path` and
`terrain_path` fixtures — running from the repo root matters for that import to resolve.

## API surface

| Method & path | Purpose |
|---|---|
| `GET /health` | Liveness check — also what the keep-alive GitHub Action pings |
| `POST /designs` | Multipart: axe file + (terrain CSV **or** synth-terrain params) + `DesignConfigIn`/`CartoucheInfoIn` JSON. Returns `202` + `{job_id}` immediately; the actual build runs in a background thread. |
| `GET /designs/{id}` | Job status: `queued\|running\|done\|error`, plus REFT warnings and file availability once `done`. |
| `GET /designs/{id}/files/{kind}` | Streams one of `dxf\|xlsx\|pdf_plan\|pdf_pt`. |
| `GET /designs/{id}/preview` | JSON for the React SVG charts: plan axis + edges, TN/projet profile, Bruckner curve. Built from the engine's existing public getters via the `build_design(..., return_design=True)` hook — no new engine computation. |

Validation mirrors the engine's own rules rather than duplicating separate ones: e.g.
`CartoucheInfoIn.company_name` must be non-empty, the same rule `build_design()` already
enforces — it just surfaces as an HTTP `422` instead of a `500` raised from inside the engine.

## Job store — what "in-memory" means here

`backend/app/jobs.py` keeps jobs in a plain process-local dict, run through a
`ThreadPoolExecutor`. There is no external broker (no Celery, no Redis) — a small free-tier
container host has no room for one, and a synchronous design-generation tool doesn't need job
durability across restarts. A background sweep evicts jobs after a 30-minute TTL. **A restart
or redeploy drops every in-flight and completed job** — by design, not as a bug. If this
backend is ever repurposed for something that needs jobs to survive restarts, that's a
different architecture (external queue + storage), not a tweak to this one.

Because the build runs in a background thread *after* the HTTP response is sent, the container
must keep getting CPU while idle-of-requests. On Cloud Run that means deploying with
`--no-cpu-throttling`; other hosts allocate CPU for the instance lifetime by default.

## Docker

```bash
# from the repo root — the Dockerfile lives at the repo root and its build
# context IS the repo root, so road_designer/ and samples/ are copied in
# alongside backend/.
docker build -t road-designer-api .
docker run --rm -p 8000:7860 road-designer-api
# → http://localhost:8000/health
```

The container listens on `$PORT` if set, else `7860` (so Cloud Run / Render / Koyeb / Fly and
Hugging Face Spaces all work with no change).

## Deploying

The full step-by-step is in the repo-root [`DEPLOYMENT.md`](../DEPLOYMENT.md). In short:

- **Primary: Google Cloud Run** (Part A) — `gcloud run deploy road-designer-api --source .
  --region <r> --allow-unauthenticated --memory 1Gi --no-cpu-throttling` from the repo root.
  Free monthly compute allotment covers light/moderate use; scales to zero.
- **Alternative: Hugging Face Spaces** (Part G) — now needs a **PRO** plan for CPU hardware.
  SDK = Docker, Dockerfile at the Space repo root, port 7860 auto-selected.
- **No-card alternatives:** Render / Koyeb free web services (512 MB, ~50 s cold start).

The Dockerfile is host-neutral, so switching hosts later is: build the same image there,
repoint `VITE_API_BASE_URL` on Cloudflare Pages, re-set `ALLOWED_ORIGIN`.

## Env vars / secrets to fill in after first real deploy

| Where | Name | Set to |
|---|---|---|
| Backend host (Cloud Run: `--set-env-vars`; HF: Space Variables) | `ALLOWED_ORIGIN` | The deployed Cloudflare Pages origin, e.g. `https://road-designer.pages.dev` |
| Cloudflare Pages dashboard | `VITE_API_BASE_URL` | The backend's public URL, no trailing slash (see `frontends/react/README.md`) |
| GitHub repo secret (optional) | `BACKEND_HEALTH_URL` | `https://<backend-host>/health` — used by `.github/workflows/keep-alive-backend.yml`. Set it only for hosts where staying warm is free (HF / Render / Koyeb); **not** for Cloud Run with `--no-cpu-throttling`. |

## Directory layout

```
backend/
├── app/
│   ├── main.py          ← FastAPI() instance, CORS via ALLOWED_ORIGIN, lifespan-managed cleanup task
│   ├── schemas.py        ← Pydantic DesignConfigIn/TypicalSectionIn/CartoucheInfoIn/SynthTerrainParams
│   ├── jobs.py           ← in-memory job dict + ThreadPoolExecutor runner + 30-min TTL sweep
│   └── routers/
│       ├── designs.py    ← POST /designs, GET /designs/{id}, GET /designs/{id}/files/{kind}
│       ├── preview.py    ← GET /designs/{id}/preview
│       └── health.py     ← GET /health
├── requirements.txt
└── tests/
    ├── conftest.py
    └── test_designs.py
```
