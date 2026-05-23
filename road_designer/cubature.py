"""Earthwork volumes (cubatures) and mass-haul diagram (Bruckner).

Phase 1a — plateforme approximation
-----------------------------------
The cross-section area at PK is approximated as a trapezoid:

    A(pk) = |h| × (W/2 + |h| × m)

where
    h  = Z_projet(pk) − Z_TN(pk)   (signed; >0 ⇒ remblai, <0 ⇒ déblai)
    W  = platform width            (cfg.road_width)
    m  = talus ratio H/V           (cfg.typical_section.talus_*)

Volume between two adjacent stations uses the **moyenne des aires**:

    V = ½ × (A₁ + A₂) × ΔPK

Sign convention
---------------
Per segment we return TWO non-negative numbers, ``V_deb`` and ``V_rem``:
- if both endpoints are remblai → V_deb = 0,  V_rem = average
- if both endpoints are déblai  → V_deb = average, V_rem = 0
- if signs differ (transition) → split the segment at the h=0 crossing and
  attribute each side to its category. This is essential for an honest
  Bruckner — without it transitions get smeared and the mass-haul diagram
  hides the natural haul boundaries.

Bruckner
--------
``M(pk) = Σ_{k=0..k(pk)} (V_rem[k] − V_deb[k])``

Phase 1b (later, Step 7b) will replace ``area_plateforme`` with a polygon
area computed by ``cross_section.py``. The rest of this module is unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, List, Tuple

import numpy as np

if TYPE_CHECKING:
    from .road_design import RoadDesign


# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class CubatureResult:
    """Per-segment + cumulative earthwork volumes, plus the Bruckner curve.

    Sizes
    -----
    For N station vertices there are N-1 segments. Per-vertex arrays
    (``area_per_vertex``, ``h_per_vertex``) are length N. Per-segment
    arrays are length N-1. The cumulative arrays are length N (one
    value at each vertex; first value is 0).
    """
    h_per_vertex: np.ndarray              # signed cut/fill height [m]
    area_per_vertex: np.ndarray           # signed cross-section area [m²]
    V_deb_per_seg: np.ndarray             # déblai vol per segment [m³]
    V_rem_per_seg: np.ndarray             # remblai vol per segment [m³]
    V_deb_cum: np.ndarray                 # cumulative déblai at each vertex [m³]
    V_rem_cum: np.ndarray                 # cumulative remblai at each vertex [m³]
    bruckner: np.ndarray                  # M(pk) at each vertex [m³]
    total_deb: float                      # = V_deb_per_seg.sum()
    total_rem: float                      # = V_rem_per_seg.sum()
    balance: float                        # = total_rem − total_deb


# ─────────────────────────────────────────────────────────────────────────────
# Cross-section area (plateforme approx)
# ─────────────────────────────────────────────────────────────────────────────

def area_plateforme(h: float, road_width: float,
                    talus_deblai_h_v: float,
                    talus_remblai_h_v: float) -> float:
    """Signed cross-section area for a plateforme of width W on a slope.

    Section model
    -------------
    A horizontal platform of width W is cut/filled to reach the projet line.
    Sides are sloped at ``m = H/V`` (déblai: 2/3 normal; remblai: 3/2 normal).
    The signed area is a trapezoid:

        A = h × (W + |h| × m)       with sign(A) = sign(h)
              ↑ half-width on each side: W/2 + |h|×m / 2 … = h(W + |h|m)/2 each
              ↑ total = h × (W + |h|×m)

    Note: this is a coarse first-pass area (Phase 1a). The polygon-true
    version (Phase 1b, Step 7b) replaces this function.
    """
    if h == 0:
        return 0.0
    m = talus_remblai_h_v if h > 0 else talus_deblai_h_v
    abs_a = abs(h) * (road_width + abs(h) * m)
    return abs_a if h > 0 else -abs_a


# ─────────────────────────────────────────────────────────────────────────────
# Per-segment volume with zero-crossing split
# ─────────────────────────────────────────────────────────────────────────────

def _segment_volume(
    h1: float, h2: float, a1: float, a2: float, dpk: float
) -> Tuple[float, float]:
    """Return ``(V_deb, V_rem)`` for one segment of length ``dpk``.

    Splits at the h=0 crossing if signs differ.
    """
    if dpk <= 0:
        return 0.0, 0.0

    if h1 * h2 >= 0:
        # Same sign (or one endpoint is 0) — single category
        vol = 0.5 * (abs(a1) + abs(a2)) * dpk
        if h1 + h2 >= 0:
            return 0.0, vol      # remblai
        return vol, 0.0          # déblai

    # Sign change — linearly find h=0 crossing
    t = h1 / (h1 - h2)           # fraction of segment to the zero crossing
    dpk_a = dpk * t              # part from start to zero
    dpk_b = dpk - dpk_a          # part from zero to end
    vol_a = 0.5 * abs(a1) * dpk_a   # one endpoint is zero at the crossing
    vol_b = 0.5 * abs(a2) * dpk_b
    if h1 < 0:
        return vol_a, vol_b      # start déblai → end remblai
    return vol_b, vol_a          # start remblai → end déblai


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────

def compute_cubatures(design: "RoadDesign") -> CubatureResult:
    """Build per-segment volumes + cumulatives + Bruckner from a design.

    Uses ``design.vert_pks``, ``vert_ground_z`` (TN at each vertex), and
    ``v_align.get_z(pk)`` (projet at each vertex). h is recomputed here so
    the cubatures are honest about C2 fix (cote_proj via v_align.get_z).
    """
    cfg = design.cfg
    ts = cfg.typical_section
    pks = design.vert_pks
    z_tn = design.vert_ground_z
    z_proj = np.array([design.v_align.get_z(pk) for pk in pks])
    h = z_proj - z_tn

    area = np.array([
        area_plateforme(hi, cfg.road_width,
                        ts.talus_deblai_h_v, ts.talus_remblai_h_v)
        for hi in h
    ])

    n = len(pks)
    V_deb = np.zeros(n - 1)
    V_rem = np.zeros(n - 1)
    for i in range(n - 1):
        V_deb[i], V_rem[i] = _segment_volume(
            h[i], h[i + 1], area[i], area[i + 1], pks[i + 1] - pks[i]
        )

    V_deb_cum = np.concatenate(([0.0], np.cumsum(V_deb)))
    V_rem_cum = np.concatenate(([0.0], np.cumsum(V_rem)))
    bruckner = V_rem_cum - V_deb_cum

    return CubatureResult(
        h_per_vertex=h,
        area_per_vertex=area,
        V_deb_per_seg=V_deb,
        V_rem_per_seg=V_rem,
        V_deb_cum=V_deb_cum,
        V_rem_cum=V_rem_cum,
        bruckner=bruckner,
        total_deb=float(V_deb.sum()),
        total_rem=float(V_rem.sum()),
        balance=float(V_rem.sum() - V_deb.sum()),
    )
