"""Shared fixtures for the backend test suite.

Reuses the repo-root ``tests/conftest.py`` fixtures (``axe_path``,
``terrain_path``) rather than re-deriving sample-file paths — imported as
plain names so pytest picks them up as fixtures in this package too.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest
from fastapi.testclient import TestClient

from tests.conftest import axe_path, terrain_path  # noqa: F401 — fixture reuse

from backend.app.main import app


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def valid_config_json() -> str:
    return json.dumps({
        "road_category": "CAT_1",
        "cartouche": {"company_name": "BeamStack Test"},
    })
