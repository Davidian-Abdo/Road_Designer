# SPDX-FileCopyrightText: 2026 Beamstack <https://beam-stack.com>
# SPDX-License-Identifier: LicenseRef-BCL-1.0
"""GET /health — liveness probe. Also the endpoint the optional GitHub Actions
keep-alive pinger (.github/workflows/keep-alive-backend.yml) hits to keep a
sleeping backend warm on hosts where idle time is free (HF PRO / Render /
Koyeb — not Cloud Run with --no-cpu-throttling)."""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}
