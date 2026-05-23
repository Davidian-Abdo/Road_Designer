"""Tests for cubature.py — area, segment volume sign-handling, balance."""
from __future__ import annotations

import math

import numpy as np
import pytest

from road_designer.cross_section import _polygon_area
from road_designer.cubature import (
    _segment_volume,
    area_plateforme,
    compute_cubatures,
)


# ─────────────────────────────────────────────────────────────────────────────

def test_area_plateforme_zero():
    assert area_plateforme(0.0, 7.0, 2/3, 3/2) == 0.0


def test_area_plateforme_signs():
    # Remblai positive, déblai negative
    assert area_plateforme(+1.0, 7.0, 2/3, 3/2) > 0
    assert area_plateforme(-1.0, 7.0, 2/3, 3/2) < 0


def test_area_plateforme_increasing_with_h():
    a1 = area_plateforme(1.0, 7.0, 2/3, 3/2)
    a2 = area_plateforme(2.0, 7.0, 2/3, 3/2)
    assert abs(a2) > abs(a1) * 1.5  # superlinear due to talus


def test_segment_volume_same_sign_fill():
    v_d, v_r = _segment_volume(h1=1.0, h2=1.0, a1=10.0, a2=10.0, dpk=20.0)
    assert v_d == 0.0
    assert math.isclose(v_r, 200.0)


def test_segment_volume_same_sign_cut():
    v_d, v_r = _segment_volume(h1=-1.0, h2=-1.0, a1=-10.0, a2=-10.0, dpk=20.0)
    assert v_r == 0.0
    assert math.isclose(v_d, 200.0)


def test_segment_volume_sign_change_split():
    """Half cut, half fill — both sides should be non-zero."""
    v_d, v_r = _segment_volume(h1=-1.0, h2=+1.0,
                                a1=-10.0, a2=+10.0, dpk=20.0)
    assert v_d > 0 and v_r > 0
    # Total volume ≈ average area × dpk × ½ for each half
    assert math.isclose(v_d, 50.0, rel_tol=1e-6)
    assert math.isclose(v_r, 50.0, rel_tol=1e-6)


def test_polygon_area_square():
    poly = [(0, 0), (1, 0), (1, 1), (0, 1)]
    assert math.isclose(_polygon_area(poly), 1.0)


def test_polygon_area_degenerate():
    assert _polygon_area([(0, 0), (1, 1)]) == 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Full-pipeline test via the session-scoped design fixture
# ─────────────────────────────────────────────────────────────────────────────

def test_compute_cubatures_basic(design):
    cub = design.cubatures
    n = len(design.vert_pks)
    assert cub.h_per_vertex.shape == (n,)
    assert cub.V_deb_per_seg.shape == (n - 1,)
    assert cub.V_rem_per_seg.shape == (n - 1,)
    assert (cub.V_deb_per_seg >= 0).all()
    assert (cub.V_rem_per_seg >= 0).all()


def test_balance_matches_totals(design):
    cub = design.cubatures
    assert math.isclose(cub.balance, cub.total_rem - cub.total_deb,
                        rel_tol=1e-9)


def test_cumulatives_monotonic(design):
    cub = design.cubatures
    # Cumulative déblai and remblai are non-decreasing
    assert (np.diff(cub.V_deb_cum) >= -1e-9).all()
    assert (np.diff(cub.V_rem_cum) >= -1e-9).all()


def test_bruckner_endpoints(design):
    cub = design.cubatures
    assert math.isclose(cub.bruckner[0], 0.0, abs_tol=1e-9)
    assert math.isclose(cub.bruckner[-1], cub.balance, abs_tol=1e-6)
