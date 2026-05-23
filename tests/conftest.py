"""Shared pytest fixtures for Road Designer V 1.0 tests."""
from __future__ import annotations

import sys
from pathlib import Path

# Make the project root importable regardless of where pytest is launched
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest

from road_designer.config import REFT_CAT_1
from road_designer.samples_api import sample_axe_path, sample_terrain_path


@pytest.fixture(scope="session")
def axe_path() -> Path:
    return sample_axe_path()


@pytest.fixture(scope="session")
def terrain_path() -> Path:
    return sample_terrain_path()


@pytest.fixture(scope="session")
def cfg():
    """A fresh CAT_1 config for every session."""
    from copy import deepcopy
    return deepcopy(REFT_CAT_1)


@pytest.fixture(scope="session")
def design(axe_path, terrain_path, cfg):
    """A built RoadDesign with cubatures attached. Expensive — session-scoped."""
    from road_designer.cross_section import all_sections
    from road_designer.cubature import compute_cubatures
    from road_designer.road_design import RoadDesign

    d = RoadDesign(terrain_path, axe_path, cfg)
    sections = all_sections(d)
    d.section_areas = {s.pk: (s.cut_area, s.fill_area) for s in sections}
    d.sections = sections
    d.cubatures = compute_cubatures(d)
    return d
