"""2D geometry helpers used by plan-view rendering and cross-section sampling."""
from __future__ import annotations

import numpy as np


def compute_normal(dx: float, dy: float) -> np.ndarray:
    """Unit normal (left-hand) to direction (dx, dy). Returns (0,0) on a zero vector."""
    length = np.hypot(dx, dy)
    if length == 0:
        return np.array([0.0, 0.0])
    # 90° CCW: (-dy, dx) / |v|
    return np.array([-dy / length, dx / length])


def offset_points(axis_points: np.ndarray, road_width: float):
    """For each point on the axis, return (left, right) edge points at ±W/2."""
    lefts, rights = [], []
    n = len(axis_points)
    for i in range(n):
        if i == 0:
            dx = axis_points[i + 1, 0] - axis_points[i, 0]
            dy = axis_points[i + 1, 1] - axis_points[i, 1]
        elif i == n - 1:
            dx = axis_points[i, 0] - axis_points[i - 1, 0]
            dy = axis_points[i, 1] - axis_points[i - 1, 1]
        else:
            dx = axis_points[i + 1, 0] - axis_points[i - 1, 0]
            dy = axis_points[i + 1, 1] - axis_points[i - 1, 1]
        n_vec = compute_normal(dx, dy)
        lefts.append(axis_points[i] + n_vec * (road_width / 2))
        rights.append(axis_points[i] - n_vec * (road_width / 2))
    return np.array(lefts), np.array(rights)


def cutting_line_points(axis_point: np.ndarray, normal: np.ndarray, length: float):
    """Two endpoints of a cutting line centred on ``axis_point``."""
    half = length / 2
    return axis_point + normal * half, axis_point - normal * half


def rotate_points(points: np.ndarray, angle: float) -> np.ndarray:
    """Rotate Nx2 points by ``angle`` radians (CCW)."""
    rot = np.array([[np.cos(angle), -np.sin(angle)],
                    [np.sin(angle),  np.cos(angle)]])
    return np.dot(points, rot.T)


def rotate_vector(v: np.ndarray, angle: float) -> np.ndarray:
    """Rotate a 2-vector by ``angle`` radians (CCW)."""
    rot = np.array([[np.cos(angle), -np.sin(angle)],
                    [np.sin(angle),  np.cos(angle)]])
    return np.dot(rot, v)
