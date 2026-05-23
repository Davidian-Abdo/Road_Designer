"""Profils en travers — typical section construction + per-PK cross-section.

For every requested PK the module:

  1. Samples TN along the perpendicular to the axis (±``extent`` m).
  2. Builds the projet section from ``TypicalSection``:
        chaussée  ─ accotement ─ fossé ─ talus
     anchored at ``v_align.get_z(pk)``.
  3. Closes the talus polylines against TN so cut/fill polygons are bounded.
  4. Returns a ``CrossSectionResult`` with both projet + TN polylines and the
     **two signed polygon areas** ``cut_area`` and ``fill_area``.

The polygon area is what Step 7b feeds back to ``cubature.py`` to replace the
plateforme approximation.

Geometry coordinate system
--------------------------
All cross-section coordinates are LOCAL: ``t`` is the perpendicular offset
in metres from the axis (negative = left, positive = right), ``z`` is the
absolute elevation. The DXF rendering scales ``z`` by the section's V scale
and ``t`` by the H scale.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, List, Tuple

import numpy as np

from .geometry_engine import compute_normal

if TYPE_CHECKING:
    from .road_design import RoadDesign


# ─────────────────────────────────────────────────────────────────────────────
# Result container
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class CrossSectionResult:
    pk: float
    tn_polyline: List[Tuple[float, float]]       # (t, z) — TN samples
    proj_polyline: List[Tuple[float, float]]     # (t, z) — projet platform
    cut_polygons: List[List[Tuple[float, float]]]   # déblai polygons
    fill_polygons: List[List[Tuple[float, float]]]  # remblai polygons
    cut_area: float = 0.0                          # m² (>= 0)
    fill_area: float = 0.0                         # m² (>= 0)
    z_axis_proj: float = 0.0                       # projet elevation at t=0
    z_axis_tn: float = 0.0                         # TN elevation at t=0
    # Break points on the projet line, useful for cotation
    projet_break_points: List[Tuple[float, float, str]] = field(
        default_factory=list
    )  # (t, z, label)


# ─────────────────────────────────────────────────────────────────────────────
# Typical-section construction (projet line)
# ─────────────────────────────────────────────────────────────────────────────

def _build_projet_half(ts, z_axis: float, side: int):
    """Build the projet polyline on one side of the axis.

    Returns a list of (t, z) running from the axis (t=0) outward.
    ``side`` = +1 right, -1 left.
    """
    pts: List[Tuple[float, float, str]] = [(0.0, z_axis, "axe")]

    # 1) Chaussée crown
    t_chau = ts.chaussee_width / 2
    z_chau = z_axis - ts.crown_slope * t_chau
    pts.append((side * t_chau, z_chau, "bord chaussée"))

    # 2) Accotement
    t_acco = t_chau + ts.accotement_width
    z_acco = z_chau - ts.accotement_slope * ts.accotement_width
    pts.append((side * t_acco, z_acco, "bord accotement"))

    # 3) Fossé (triangulaire) — the road shoulder drops to ditch bottom
    t_ditch_in = t_acco
    z_ditch_bot = z_acco - ts.ditch_depth
    t_ditch_bot = t_ditch_in + ts.ditch_width / 2
    t_ditch_out = t_ditch_in + ts.ditch_width
    z_ditch_out = z_acco
    pts.append((side * t_ditch_bot, z_ditch_bot, "fond fossé"))
    pts.append((side * t_ditch_out, z_ditch_out, "berge fossé"))

    return pts


def build_projet_polyline(ts, z_axis: float
                          ) -> List[Tuple[float, float, str]]:
    """Full projet polyline (left → axis → right) with break-point labels."""
    left = list(reversed(_build_projet_half(ts, z_axis, side=-1)))
    right = _build_projet_half(ts, z_axis, side=+1)[1:]  # drop axis duplicate
    return left + right


# ─────────────────────────────────────────────────────────────────────────────
# Talus closure against TN
# ─────────────────────────────────────────────────────────────────────────────

def _extend_talus(t_start, z_start, side: int, hv_ratio: float,
                  going_down: bool, tn_t, tn_z, max_extent: float):
    """Extend a talus line from (t_start, z_start) outward (``side``) until
    it crosses TN, then return the crossing point.

    ``hv_ratio`` is H/V (e.g. 2/3 for déblai → for each 3 m vertical the talus
    runs 2 m horizontal). ``going_down`` chooses talus orientation.
    """
    direction = 1.0 if going_down else -1.0   # +1 = sloping down outward

    # Talus parametric: t(s) = t_start + side*s ; z(s) = z_start - direction*s/hv_ratio
    # Find s where talus = TN(t)
    # We discretise along ``s``.
    s_max = max_extent
    s_grid = np.linspace(0.0, s_max, 400)
    t_grid = t_start + side * s_grid
    z_talus = z_start - direction * s_grid / hv_ratio if hv_ratio > 0 else \
        np.full_like(s_grid, z_start)
    z_tn_grid = np.interp(t_grid, tn_t, tn_z,
                          left=tn_z[0], right=tn_z[-1])
    diff = z_talus - z_tn_grid
    # First sign change in ``diff`` is the meeting point
    sign = np.sign(diff)
    cross = np.where(np.diff(sign) != 0)[0]
    if cross.size == 0:
        # Talus never meets TN within max_extent — clamp to extent
        return (float(t_grid[-1]), float(z_talus[-1]))
    idx = int(cross[0])
    # Linear interp between idx and idx+1
    d0, d1 = diff[idx], diff[idx + 1]
    frac = d0 / (d0 - d1) if (d0 - d1) != 0 else 0.5
    t_cross = t_grid[idx] + (t_grid[idx + 1] - t_grid[idx]) * frac
    z_cross = z_talus[idx] + (z_talus[idx + 1] - z_talus[idx]) * frac
    return (float(t_cross), float(z_cross))


# ─────────────────────────────────────────────────────────────────────────────
# Polygon area (shoelace) and cut/fill polygon assembly
# ─────────────────────────────────────────────────────────────────────────────

def _polygon_area(poly: List[Tuple[float, float]]) -> float:
    """Absolute polygon area (shoelace). ``poly`` must be ordered."""
    if len(poly) < 3:
        return 0.0
    a = 0.0
    for i in range(len(poly)):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % len(poly)]
        a += x1 * y2 - x2 * y1
    return abs(a) / 2.0


def _cut_fill_polygons(
    tn_t: np.ndarray, tn_z: np.ndarray,
    proj_t: np.ndarray, proj_z: np.ndarray,
):
    """Build cut/fill polygons by walking the merged t-grid and grouping
    consecutive samples where ``proj < tn`` (cut) or ``proj > tn`` (fill).

    Returns (cut_polys, fill_polys, cut_area, fill_area).
    """
    # Merge t-grids
    t_all = np.unique(np.concatenate([tn_t, proj_t]))
    z_tn = np.interp(t_all, tn_t, tn_z)
    z_pj = np.interp(t_all, proj_t, proj_z)
    h = z_pj - z_tn      # >0 fill, <0 cut

    # Group consecutive samples of the same sign
    sign = np.sign(h)
    # Treat exact zeros as boundaries
    cut_polys: List[List[Tuple[float, float]]] = []
    fill_polys: List[List[Tuple[float, float]]] = []
    i = 0
    n = len(t_all)
    while i < n:
        if sign[i] == 0:
            i += 1
            continue
        j = i
        while j < n and sign[j] == sign[i]:
            j += 1
        # Group [i, j)
        seg_t = t_all[i:j]
        # Extend each side to the previous/next zero crossing
        seg_tn_z = z_tn[i:j]
        seg_pj_z = z_pj[i:j]
        if i > 0:
            # Insert zero-crossing on the left
            t0, t1 = t_all[i - 1], t_all[i]
            h0, h1 = h[i - 1], h[i]
            tc = t0 + (t1 - t0) * (-h0 / (h1 - h0)) if (h1 - h0) != 0 else t1
            zc = np.interp(tc, tn_t, tn_z)
            seg_t = np.concatenate([[tc], seg_t])
            seg_tn_z = np.concatenate([[zc], seg_tn_z])
            seg_pj_z = np.concatenate([[zc], seg_pj_z])
        if j < n:
            t0, t1 = t_all[j - 1], t_all[j]
            h0, h1 = h[j - 1], h[j]
            tc = t0 + (t1 - t0) * (-h0 / (h1 - h0)) if (h1 - h0) != 0 else t1
            zc = np.interp(tc, tn_t, tn_z)
            seg_t = np.concatenate([seg_t, [tc]])
            seg_tn_z = np.concatenate([seg_tn_z, [zc]])
            seg_pj_z = np.concatenate([seg_pj_z, [zc]])

        poly = [(float(t), float(z)) for t, z in zip(seg_t, seg_pj_z)]
        poly.extend(
            (float(t), float(z))
            for t, z in zip(seg_t[::-1], seg_tn_z[::-1])
        )
        if sign[i] > 0:
            fill_polys.append(poly)
        else:
            cut_polys.append(poly)
        i = j

    cut_area = sum(_polygon_area(p) for p in cut_polys)
    fill_area = sum(_polygon_area(p) for p in fill_polys)
    return cut_polys, fill_polys, cut_area, fill_area


# ─────────────────────────────────────────────────────────────────────────────
# Per-PK cross-section
# ─────────────────────────────────────────────────────────────────────────────

def section_at_pk(design: "RoadDesign", pk: float) -> CrossSectionResult:
    """Build the full cross-section at ``pk``."""
    cfg = design.cfg
    ts = cfg.typical_section

    # 1) Axis point and normal at PK
    x_ax, y_ax, dx, dy = _axis_point_and_tangent(design, pk)
    nx, ny = compute_normal(dx, dy)

    # 2) TN samples
    extent = cfg.cross_section_extent
    step = max(0.5, extent / 30)
    t_vals = np.arange(-extent, extent + step, step)
    tn_z = np.array([
        design.terrain.query_z(x_ax + nx * t, y_ax + ny * t)
        for t in t_vals
    ])

    # 3) Projet section anchored at v_align.get_z(pk)
    z_axis = float(design.v_align.get_z(pk))
    projet_pts = build_projet_polyline(ts, z_axis)

    # 4) Close talus on each side against TN
    left_end = projet_pts[0]    # outermost left point (berge fossé gauche)
    right_end = projet_pts[-1]  # outermost right point
    z_tn_left = float(np.interp(left_end[0], t_vals, tn_z))
    z_tn_right = float(np.interp(right_end[0], t_vals, tn_z))
    talus_left = _extend_talus(
        left_end[0], left_end[1], side=-1,
        hv_ratio=(ts.talus_remblai_h_v if z_tn_left < left_end[1]
                  else ts.talus_deblai_h_v),
        going_down=(z_tn_left < left_end[1]),
        tn_t=t_vals, tn_z=tn_z, max_extent=extent,
    )
    talus_right = _extend_talus(
        right_end[0], right_end[1], side=+1,
        hv_ratio=(ts.talus_remblai_h_v if z_tn_right < right_end[1]
                  else ts.talus_deblai_h_v),
        going_down=(z_tn_right < right_end[1]),
        tn_t=t_vals, tn_z=tn_z, max_extent=extent,
    )

    # Full projet polyline (with talus appended) for rendering
    proj_full = (
        [talus_left]
        + [(p[0], p[1]) for p in projet_pts]
        + [talus_right]
    )

    # Break-point labels for cotation
    proj_breaks = [(p[0], p[1], p[2]) for p in projet_pts]

    # 5) Cut/fill polygons + areas
    proj_arr = np.array(proj_full)
    cut_polys, fill_polys, cut_a, fill_a = _cut_fill_polygons(
        t_vals, tn_z, proj_arr[:, 0], proj_arr[:, 1],
    )

    return CrossSectionResult(
        pk=pk,
        tn_polyline=list(zip(map(float, t_vals), map(float, tn_z))),
        proj_polyline=proj_full,
        cut_polygons=cut_polys,
        fill_polygons=fill_polys,
        cut_area=cut_a,
        fill_area=fill_a,
        z_axis_proj=z_axis,
        z_axis_tn=float(np.interp(0.0, t_vals, tn_z)),
        projet_break_points=proj_breaks,
    )


def _axis_point_and_tangent(design: "RoadDesign", pk: float):
    """Return (x, y, dx, dy) at PK by walking the segments."""
    for seg in design.segments:
        if seg.start_pk <= pk <= seg.end_pk:
            d = pk - seg.start_pk
            pt = seg.point_at_distance(d)
            tng = seg.direction_at_distance(d)
            return float(pt[0]), float(pt[1]), float(tng[0]), float(tng[1])
    # Fallback: clamp
    seg = design.segments[0] if pk < design.segments[0].start_pk else design.segments[-1]
    d = max(0.0, min(seg.length, pk - seg.start_pk))
    pt = seg.point_at_distance(d)
    tng = seg.direction_at_distance(d)
    return float(pt[0]), float(pt[1]), float(tng[0]), float(tng[1])


# ─────────────────────────────────────────────────────────────────────────────
# Batch helper
# ─────────────────────────────────────────────────────────────────────────────

def all_sections(design: "RoadDesign") -> List[CrossSectionResult]:
    """Return one ``CrossSectionResult`` per station vertex, filtered by
    ``cfg.cross_section_step_pk``."""
    step = max(1, design.cfg.cross_section_step_pk)
    return [
        section_at_pk(design, float(pk))
        for i, pk in enumerate(design.vert_pks)
        if i % step == 0 or i == len(design.vert_pks) - 1
    ]
