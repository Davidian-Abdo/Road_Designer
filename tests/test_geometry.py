"""Tests for geometry_engine.py — normal, offset, rotation."""
from __future__ import annotations

import math

import numpy as np

from road_designer.geometry_engine import (
    compute_normal,
    offset_points,
    rotate_points,
    rotate_vector,
)


def test_compute_normal_unit_length():
    n = compute_normal(3.0, 4.0)
    assert math.isclose(np.linalg.norm(n), 1.0)


def test_compute_normal_perpendicular():
    n = compute_normal(2.0, 0.0)
    assert math.isclose(np.dot([2, 0], n), 0.0, abs_tol=1e-9)


def test_compute_normal_zero_vector():
    assert (compute_normal(0.0, 0.0) == np.array([0.0, 0.0])).all()


def test_offset_points_straight():
    axis = np.column_stack((np.linspace(0, 10, 11), np.zeros(11)))
    left, right = offset_points(axis, road_width=4.0)
    # Left = +y by 2, right = -y by 2
    assert np.allclose(left[:, 1], 2.0)
    assert np.allclose(right[:, 1], -2.0)


def test_rotate_round_trip():
    pts = np.array([[1.0, 0.0], [0.0, 1.0], [3.5, -2.7]])
    angle = 0.73
    rt = rotate_points(rotate_points(pts, angle), -angle)
    assert np.allclose(rt, pts, atol=1e-12)


def test_rotate_vector_90_deg():
    v = np.array([1.0, 0.0])
    r = rotate_vector(v, math.pi / 2)
    assert np.allclose(r, [0.0, 1.0], atol=1e-12)
