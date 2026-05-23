"""Vertical alignment (ligne rouge) with parabolic curves at each PVI.

Per-curve radius is chosen as the maximum feasible radius given the tangent
length to the previous/next PVI, capped by ``max_radius`` and floored by REFT
minima (``r_summit`` / ``r_sag``).

Bug C4 (was ``smothing_factor``) is renamed at the call site to
``vertical_band_ratio`` — this module never sees that parameter directly.

Bug C6 (``min_straight_tangent``) is enforced by ``check_curve_overlap`` which
the SLSQP optimiser uses as a constraint.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Union

import numpy as np


@dataclass
class Curve:
    """A single parabolic vertical curve straddling one PVI."""
    pvi_idx: int
    start: float       # PK of PVC
    end: float         # PK of PVT
    R: float           # K-value (a.k.a. radius) [m/%]
    L: float           # curve length [m]
    g1: float          # incoming grade (fraction, e.g. 0.05 = 5 %)
    sign: float        # +1 for sag (cuvette), -1 for summit (sommet)


class VerticalAlignment:
    """Parabolic vertical alignment from a sparse list of PVIs."""

    def __init__(
        self,
        pvi_list,
        min_summit: float,
        min_sag: float,
        safety_factor: float = 0.95,
        target_mode: str = "max",
        desired_radius: Optional[Union[float, List[float]]] = None,
        max_radius: Optional[float] = None,
    ):
        self.pvi = np.asarray(pvi_list, dtype=float)
        self.min_summit = float(min_summit)
        self.min_sag = float(min_sag)
        self.safety_factor = float(safety_factor)
        self.target_mode = target_mode
        self.desired_radius = desired_radius
        self.max_radius = max_radius
        self.grades: List[float] = []
        self.curves: List[dict] = []
        self._compute_curves()

    # ------------------------------------------------------------------ core

    def _compute_curves(self):
        n = len(self.pvi)
        self.grades = []
        for i in range(n - 1):
            dz = self.pvi[i + 1, 1] - self.pvi[i, 1]
            dpk = self.pvi[i + 1, 0] - self.pvi[i, 0]
            self.grades.append(dz / dpk if dpk != 0 else 0.0)

        self.curves = []
        for i in range(1, n - 1):
            g1, g2 = self.grades[i - 1], self.grades[i]
            delta_g = g2 - g1
            abs_dg = abs(delta_g)
            if abs_dg < 1e-6:
                continue

            pk_pvi = self.pvi[i, 0]
            dist_prev = pk_pvi - self.pvi[i - 1, 0]
            dist_next = self.pvi[i + 1, 0] - pk_pvi
            L_max_allowed = min(dist_prev, dist_next) * self.safety_factor
            R_max = L_max_allowed / abs_dg

            if self.target_mode == "max":
                R = R_max
            elif self.target_mode == "fixed" and self.desired_radius is not None:
                des = (self.desired_radius[i - 1]
                       if isinstance(self.desired_radius, (list, tuple))
                       else self.desired_radius)
                R = min(des, R_max)
            else:
                R = R_max

            if self.max_radius is not None:
                R = min(R, self.max_radius)

            # REFT minimum
            if delta_g > 0:
                min_rad = self.min_sag    # cuvette
            else:
                min_rad = self.min_summit  # sommet
            if R < min_rad:
                print(
                    f"Warning: PVI at PK {pk_pvi:.3f} requires R={R:.0f} m "
                    f"< minimum {min_rad:.0f} m — using minimum."
                )
                R = min_rad

            L = abs_dg * R
            self.curves.append({
                "pvi_idx": i,
                "start": pk_pvi - L / 2,
                "end": pk_pvi + L / 2,
                "R": R,
                "L": L,
                "g1": g1,
                "sign": 1.0 if delta_g > 0 else -1.0,
            })

    # ------------------------------------------------------------------ API

    def get_z(self, pk: float) -> float:
        """Project elevation at ``pk`` (extrapolation clamps to endpoints)."""
        if pk <= self.pvi[0, 0]:
            return float(self.pvi[0, 1])
        if pk >= self.pvi[-1, 0]:
            return float(self.pvi[-1, 1])

        for c in self.curves:
            if c["start"] <= pk <= c["end"]:
                x = pk - c["start"]
                g1 = c["g1"]
                g2 = self.grades[c["pvi_idx"]]
                L = c["L"]
                pvi_pk, pvi_z = self.pvi[c["pvi_idx"]]
                y_pvc = pvi_z - (g1 * (L / 2.0))
                return float(y_pvc + (g1 * x) + ((g2 - g1) / (2 * L)) * (x ** 2))

        for i in range(len(self.pvi) - 1):
            if self.pvi[i, 0] <= pk <= self.pvi[i + 1, 0]:
                return float(self.pvi[i, 1] + self.grades[i] * (pk - self.pvi[i, 0]))

        return float(self.pvi[-1, 1])

    def check_curve_overlap(self, min_straight_tangent: float = 0.0) -> List[str]:
        """Return a list of warnings if two adjacent curves leave less than
        ``min_straight_tangent`` of actual straight between them (C6)."""
        warnings = []
        for ca, cb in zip(self.curves, self.curves[1:]):
            gap = cb["start"] - ca["end"]
            if gap < min_straight_tangent:
                warnings.append(
                    f"Tangente droite trop courte entre PVI #{ca['pvi_idx']} "
                    f"et #{cb['pvi_idx']}: {gap:.1f} m < "
                    f"{min_straight_tangent:.1f} m (min REFT)."
                )
        return warnings
