"""GET /health — used by the GitHub Actions keep-alive pinger
(.github/workflows/keep-alive-hf-space.yml) to stop the HF Space free-tier
container from going to sleep."""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}
