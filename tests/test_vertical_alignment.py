"""Tests for VerticalAlignment — parabolic continuity, REFT minima, C6."""
from __future__ import annotations

import math

import numpy as np
import pytest

from road_designer.design_logic import VerticalAlignment


def _make_v(z_pvi=(100.0, 105.0, 100.0)):
    pvi = np.column_stack(([0.0, 500.0, 1000.0], list(z_pvi)))
    return VerticalAlignment(pvi, min_summit=1500, min_sag=1000,
                             safety_factor=0.95, max_radius=10000)


# ─────────────────────────────────────────────────────────────────────────────

def test_endpoint_clamp():
    v = _make_v()
    assert math.isclose(v.get_z(-100), v.pvi[0, 1])
    assert math.isclose(v.get_z(1500), v.pvi[-1, 1])


def test_continuity_at_pvc_pvt():
    """get_z should be continuous across the PVC and PVT of each curve."""
    v = _make_v()
    for c in v.curves:
        z_before = v.get_z(c["start"] - 0.001)
        z_at     = v.get_z(c["start"])
        z_after  = v.get_z(c["start"] + 0.001)
        assert abs(z_at - z_before) < 1e-2
        assert abs(z_at - z_after)  < 1e-2

        z_before = v.get_z(c["end"] - 0.001)
        z_at     = v.get_z(c["end"])
        z_after  = v.get_z(c["end"] + 0.001)
        assert abs(z_at - z_before) < 1e-2
        assert abs(z_at - z_after)  < 1e-2


def test_summit_sign():
    """Down-up = sag, up-down = summit. The .sign field encodes this."""
    v_summit = _make_v(z_pvi=(0, 10, 0))   # up then down → summit
    v_sag    = _make_v(z_pvi=(10, 0, 10))  # down then up → sag
    assert v_summit.curves[0]["sign"] == -1.0
    assert v_sag.curves[0]["sign"] == +1.0


def test_min_radius_enforced():
    """Tight V-shape should be floored to min_summit."""
    pvi = np.column_stack(([0.0, 100.0, 200.0], [0.0, 5.0, 0.0]))
    v = VerticalAlignment(pvi, min_summit=2000, min_sag=2000,
                          safety_factor=0.95)
    assert v.curves[0]["R"] >= 2000 - 1e-6


def test_check_curve_overlap_warns():
    """Two PVIs close enough to give a short straight tangent must warn
    when min_straight_tangent is configured."""
    # Three PVIs with a small middle interval — the two curves around the
    # middle PVI will touch each other.
    pvi = np.column_stack(([0.0, 100.0, 105.0, 300.0],
                           [0.0, 4.0,   0.0,   4.0]))
    v = VerticalAlignment(pvi, min_summit=1500, min_sag=1000,
                          safety_factor=0.95)
    warnings = v.check_curve_overlap(min_straight_tangent=50.0)
    assert any("Tangente droite trop courte" in w for w in warnings)


def test_check_curve_overlap_clean():
    """Long straight between curves → no warning."""
    pvi = np.column_stack(([0.0, 500.0, 1500.0, 2500.0],
                           [0.0, 5.0,   -5.0,   5.0]))
    v = VerticalAlignment(pvi, min_summit=1500, min_sag=1000)
    assert v.check_curve_overlap(min_straight_tangent=10.0) == []
