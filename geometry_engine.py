import numpy as np

def compute_normal(dx, dy):
    """Unit normal vector (perpendicular) to direction (dx, dy)."""
    length = np.hypot(dx, dy)
    if length == 0:
        return np.array([0.0, 0.0])
    # Rotate 90° counter‑clockwise: (-dy, dx) / length
    return np.array([-dy / length, dx / length])

def offset_points(axis_points, road_width):
    """For each point on the axis, compute left and right edge points."""
    lefts, rights = [], []
    n = len(axis_points)
    for i in range(n):
        if i == 0:
            dx = axis_points[i+1, 0] - axis_points[i, 0]
            dy = axis_points[i+1, 1] - axis_points[i, 1]
        elif i == n-1:
            dx = axis_points[i, 0] - axis_points[i-1, 0]
            dy = axis_points[i, 1] - axis_points[i-1, 1]
        else:
            dx = axis_points[i+1, 0] - axis_points[i-1, 0]
            dy = axis_points[i+1, 1] - axis_points[i-1, 1]
        n_vec = compute_normal(dx, dy)
        left = axis_points[i] + n_vec * (road_width / 2)
        right = axis_points[i] - n_vec * (road_width / 2)
        lefts.append(left)
        rights.append(right)
    return np.array(lefts), np.array(rights)

def cutting_line_points(axis_point, normal, length):
    """Return two points of a cutting line centered on axis_point."""
    half = length / 2
    p1 = axis_point + normal * half
    p2 = axis_point - normal * half
    return p1, p2