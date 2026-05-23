"""RoadDesign — top-level orchestrator.

Combines TerrainModel + AlignmentParser + VerticalAlignment and exposes
geometry ready for DXF assembly and Excel export.

Step 2 (this file): the profile and the data table are indexed by **PK**
(``self.pk_axis_x``), not by rotated plan X (``self.vert_x_rot``). The plan view
keeps rotated X. The two are linked only by the rappel lines (slanted, see
``get_rappel_segments``).

Cubatures (Step 3) and Bruckner (Step 5) are computed in ``cubature.py`` and
attached here via ``self.cubatures``.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Optional, Tuple, Union

import numpy as np
from scipy.interpolate import UnivariateSpline
from scipy.optimize import Bounds, minimize

from .axe_parser import AlignmentParser
from .config import DesignConfig
from .design_logic import VerticalAlignment
from .geometry_engine import offset_points, rotate_points, rotate_vector
from .mnt_engine import TerrainModel


# ─────────────────────────────────────────────────────────────────────────────

class RoadDesign:
    """Bundle of all geometry needed by the DXF/Excel exporters."""

    # ────────────────────────────────────────────────────────────── __init__

    def __init__(
        self,
        terrain_csv: Union[str, Path],
        axe_txt: Union[str, Path],
        cfg: DesignConfig,
    ):
        self.cfg = cfg
        self.terrain = TerrainModel(terrain_csv)
        self.parser = AlignmentParser(axe_txt)
        self.segments = self.parser.parse()
        self.station_vertices = self.parser.station_points

        if not self.station_vertices:
            raise ValueError("No station points found in axe file.")

        # 1. Station vertices (PK, X, Y) ─────────────────────────────────
        self.vert_pks = np.array([v[0] for v in self.station_vertices])
        self.vert_x = np.array([v[1] for v in self.station_vertices])
        self.vert_y = np.array([v[2] for v in self.station_vertices])

        # 2. Plan-view rotation (drawing only — never propagates to math) ─
        dx, dy = (self.vert_x[-1] - self.vert_x[0],
                  self.vert_y[-1] - self.vert_y[0])
        self.road_angle = float(np.arctan2(dy, dx))
        self.rot_angle = -self.road_angle
        vert_rot = rotate_points(
            np.column_stack((self.vert_x, self.vert_y)), self.rot_angle
        )
        self.vert_x_rot, self.vert_y_rot = vert_rot[:, 0], vert_rot[:, 1]

        # 3. PK-based axis (Step 2 / bug C1) ──────────────────────────────
        # Independent variable for profile + table + Bruckner. Plan keeps
        # the rotated X; the two coordinate systems meet only at rappel
        # lines (see get_rappel_segments).
        self.pk0 = float(self.vert_pks[0])
        self.pk_axis_x = (self.vert_pks - self.pk0) * cfg.h_scale

        # 4. TN at vertices and at dense samples ─────────────────────────
        self.vert_ground_z = np.array([
            self.terrain.query_z(x, y)
            for _, x, y in self.station_vertices
        ])
        self.dense_points = self.parser.sample_points(cfg.profile_sampling)
        self.dense_pks = np.array([p[0] for p in self.dense_points])
        self.dense_ground_z = np.array([
            self.terrain.query_z(x, y) for _, x, y in self.dense_points
        ])
        # Plan-view dense rotated coords (for the smooth axis polyline)
        dense_xy = np.array([[x, y] for _, x, y in self.dense_points])
        dense_rot = rotate_points(dense_xy, self.rot_angle)
        self.dense_x_rot, self.dense_y_rot = dense_rot[:, 0], dense_rot[:, 1]
        # PK-based dense X (for the smooth profile polyline)
        self.dense_pk_x = (self.dense_pks - self.pk0) * cfg.h_scale

        # 5. Vertical design — optimise PVIs then build the curves ───────
        pvi_points = self.generate_optimized_pvis()
        self.v_align = VerticalAlignment(
            pvi_points,
            min_summit=cfg.r_summit,
            min_sag=cfg.r_sag,
            safety_factor=cfg.safety_factor,
            target_mode="max",
            max_radius=cfg.max_radius,
        )

        # C6: warn about short straight tangents between curves
        self.tangent_warnings = self.v_align.check_curve_overlap(
            cfg.min_straight_tangent
        )
        for w in self.tangent_warnings:
            print(f"REFT warning: {w}")

        # 6. Project elevations ──────────────────────────────────────────
        # Bug C2: ALWAYS via v_align.get_z(pk), never by interpolating the
        # rotated-X profile line.
        self.vert_proj_z = np.array(
            [self.v_align.get_z(pk) for pk in self.vert_pks]
        )
        self.dense_proj_z = np.array(
            [self.v_align.get_z(pk) for pk in self.dense_pks]
        )

        # 7. Per-segment lengths + datum + profile baseline ──────────────
        self.seg_lengths = np.concatenate(([0], np.diff(self.vert_pks)))
        min_el = min(self.vert_ground_z.min(), self.dense_proj_z.min())
        self.datum = float(np.floor(min_el / 10) * 10)
        self.profile_base_y = float(max(self.vert_y_rot) + cfg.profile_gap_d)

        # 8. Cubatures (Step 3) — filled by cubature.attach_cubatures() ──
        self.cubatures: Optional["CubatureResult"] = None

    # ────────────────────────────────────────────────────── PVI optimisation

    def generate_optimized_pvis(self) -> np.ndarray:
        """Pick PVIs from a smoothed TN, then SLSQP-optimise their elevations.

        Constraints
        -----------
        1. ``|grade| ≤ max_pente``
        2. Curve feasibility — required curve length fits the available tangent
        3. ``min_straight_tangent`` between adjacent curve ends (C6)
        """
        cfg = self.cfg
        pks = self.vert_pks
        zs = self.vert_ground_z

        # Pick PVI candidates where smoothed TN curvature exceeds threshold
        spline = UnivariateSpline(pks, zs,
                                  s=cfg.vertical_band_ratio * len(pks))
        smoothed = spline(pks)

        pvi_pks = [pks[0]]
        last_pk = pks[0]
        for i in range(1, len(pks) - 1):
            if pks[i] - last_pk < cfg.min_tangent_length:
                continue
            g_in = (smoothed[i] - smoothed[i - 1]) / (pks[i] - pks[i - 1])
            g_out = (smoothed[i + 1] - smoothed[i]) / (pks[i + 1] - pks[i])
            if abs(g_out - g_in) > cfg.max_grade_change:
                pvi_pks.append(pks[i])
                last_pk = pks[i]
        pvi_pks.append(pks[-1])

        z0 = np.interp(pvi_pks, pks, zs)
        z_amp = zs.max() - zs.min()
        delta = z_amp * cfg.vertical_band_ratio
        bounds = Bounds(z0 - delta, z0 + delta)

        constraints = self._build_grade_constraints(pvi_pks)
        result = minimize(
            self._objective,
            z0,
            args=(pvi_pks,),
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options={"maxiter": 500},
        )
        if not result.success:
            print(f"Optimisation warning: {result.message}")

        return np.column_stack((pvi_pks, result.x))

    def _objective(self, z_pvi, pvi_pks):
        """Σ |Z_projet − Z_TN| at all dense sample points."""
        v_align = VerticalAlignment(
            np.column_stack((pvi_pks, z_pvi)),
            min_summit=self.cfg.r_summit,
            min_sag=self.cfg.r_sag,
            safety_factor=self.cfg.safety_factor,
            max_radius=self.cfg.max_radius,
        )
        proj = np.array([v_align.get_z(pk) for pk in self.dense_pks])
        return float(np.sum(np.abs(proj - self.dense_ground_z)))

    def _build_grade_constraints(self, pvi_pks):
        cfg = self.cfg
        n = len(pvi_pks)
        cons = []

        # (1) Max grade between consecutive PVIs
        for i in range(n - 1):
            dpk = pvi_pks[i + 1] - pvi_pks[i]

            def grade_constr(z, idx=i, dpk=dpk):
                return cfg.max_pente / 100.0 - abs((z[idx + 1] - z[idx]) / dpk)

            cons.append({"type": "ineq", "fun": grade_constr})

        # (2) Curve length feasibility at each interior PVI
        # (3) C6: minimum straight tangent between adjacent curve ends
        for i in range(1, n - 1):
            dpk_left = pvi_pks[i] - pvi_pks[i - 1]
            dpk_right = pvi_pks[i + 1] - pvi_pks[i]

            def curve_constr(z, idx=i, dpk_left=dpk_left, dpk_right=dpk_right):
                g_left = (z[idx] - z[idx - 1]) / dpk_left
                g_right = (z[idx + 1] - z[idx]) / dpk_right
                delta_g = g_right - g_left
                R_needed = cfg.r_summit if delta_g < 0 else cfg.r_sag
                L_needed = abs(delta_g) * R_needed
                available = 2 * min(dpk_left, dpk_right) * cfg.safety_factor
                return available - L_needed

            cons.append({"type": "ineq", "fun": curve_constr})

            # C6 — straight-tangent constraint:
            # the available tangent between this PVI's curve end and the
            # next PVI's curve start must be ≥ min_straight_tangent.
            if i < n - 2:
                dpk_next_next = pvi_pks[i + 2] - pvi_pks[i + 1]

                def straight_constr(z, idx=i,
                                    dpk_left=dpk_left,
                                    dpk_right=dpk_right,
                                    dpk_nn=dpk_next_next):
                    g_left = (z[idx] - z[idx - 1]) / dpk_left
                    g_mid = (z[idx + 1] - z[idx]) / dpk_right
                    g_right = (z[idx + 2] - z[idx + 1]) / dpk_nn
                    L_this = abs(g_mid - g_left) * (
                        cfg.r_summit if (g_mid - g_left) < 0 else cfg.r_sag
                    )
                    L_next = abs(g_right - g_mid) * (
                        cfg.r_summit if (g_right - g_mid) < 0 else cfg.r_sag
                    )
                    straight = dpk_right - L_this / 2 - L_next / 2
                    return straight - cfg.min_straight_tangent

                cons.append({"type": "ineq", "fun": straight_constr})

        return cons

    # ──────────────────────────────────────────────────────── coordinate API

    def pk_to_x_rot(self, pk: float) -> float:
        """Plan-view X (rotated) for a given PK. Used for rappel lines."""
        return float(np.interp(pk, self.vert_pks, self.vert_x_rot))

    def pk_to_x(self, pk: float) -> float:
        """Profile/table X (PK-based) for a given PK."""
        return float((pk - self.pk0) * self.cfg.h_scale)

    # ─────────────────────────────────────────────────────────── plan-view API

    def get_plan_axis(self) -> np.ndarray:
        return np.column_stack((self.dense_x_rot, self.dense_y_rot))

    def get_plan_edges(self):
        axis = self.get_plan_axis()
        return offset_points(axis, self.cfg.road_width)

    def get_arc_annotations(self) -> Iterable[dict]:
        pk_to_rot = {
            pk: (x, y)
            for pk, x, y in zip(self.vert_pks, self.vert_x_rot, self.vert_y_rot)
        }
        for seg in self.segments:
            if not hasattr(seg, "radius"):
                continue
            start_xy_rot = pk_to_rot.get(seg.start_pk)
            end_xy_rot = pk_to_rot.get(seg.end_pk)
            dir_rot_start = (
                rotate_vector(seg.direction_at_distance(0), self.rot_angle)
                if start_xy_rot is not None else None
            )
            dir_rot_end = (
                rotate_vector(seg.direction_at_distance(seg.length),
                              self.rot_angle)
                if end_xy_rot is not None else None
            )

            arc_orig = []
            for i in range(self.cfg.arc_arrow_steps + 1):
                frac = i / self.cfg.arc_arrow_steps
                arc_orig.append(seg.point_at_distance(frac * seg.length))
            center = seg.center
            radius_abs = abs(seg.radius)
            outward = [
                pt + (pt - center) / radius_abs * self.cfg.arc_arrow_offset
                for pt in arc_orig
            ]
            outward_rot = rotate_points(np.array(outward), self.rot_angle)
            mid_rot = rotate_points(
                np.array([outward[len(outward) // 2]]), self.rot_angle
            )[0]

            yield {
                "type": "arc",
                "start_pk": seg.start_pk, "end_pk": seg.end_pk,
                "start_xy_rot": start_xy_rot, "end_xy_rot": end_xy_rot,
                "start_tangent_rot": dir_rot_start,
                "end_tangent_rot": dir_rot_end,
                "arrow_points_rot": outward_rot,
                "midpoint_rot": mid_rot,
                "label": f"R={seg.radius:.3f}  L={seg.length:.3f}",
                "radius": seg.radius, "length": seg.length,
            }

    def get_line_annotations(self) -> Iterable[dict]:
        for seg in self.segments:
            if hasattr(seg, "radius"):
                continue
            start_orig = np.array(seg.start)
            end_orig = np.array(seg.end)
            dir_orig = (end_orig - start_orig) / seg.length
            left_normal = np.array([-dir_orig[1], dir_orig[0]])
            off = self.cfg.straight_arrow_offset
            offset_line_rot = rotate_points(
                np.array([start_orig + left_normal * off,
                          end_orig + left_normal * off]),
                self.rot_angle,
            )
            mid_rot = rotate_points(
                np.array([(offset_line_rot[0] + offset_line_rot[1]) / 2]),
                0.0,
            )[0]
            yield {
                "type": "line",
                "offset_line_rot": offset_line_rot,
                "midpoint_rot": mid_rot,
                "label": f"L={seg.length:.3f}",
                "length": seg.length,
            }

    # ─────────────────────────────────────────────────────────── profile API

    def get_profile_data(self):
        """Return PK-based X plus TN/projet Y for the profil en long.

        Bug C1 fix: X is PK (scaled by h_scale, offset to start at 0), not
        rotated plan X.
        """
        prof_x = self.pk_axis_x
        prof_x_dense = self.dense_pk_x
        ground_y = self.profile_base_y + (self.vert_ground_z - self.datum) * self.cfg.v_scale
        proj_y = self.profile_base_y + (self.vert_proj_z - self.datum) * self.cfg.v_scale
        proj_y_dense = self.profile_base_y + (self.dense_proj_z - self.datum) * self.cfg.v_scale
        return prof_x, ground_y, proj_y, prof_x_dense, proj_y_dense, self.profile_base_y

    def get_rappel_segments(self):
        """Slanted leaders from plan vertex (rotated XY) to profile vertex
        (PK-based X, TN Y). Replaces the old vertical leaders that were
        only correct when prof_x == vert_x_rot (the C1 bug)."""
        prof_x = self.pk_axis_x
        ground_y = self.profile_base_y + (self.vert_ground_z - self.datum) * self.cfg.v_scale
        return [
            ((self.vert_x_rot[i], self.vert_y_rot[i]),
             (prof_x[i], ground_y[i]))
            for i in range(len(self.vert_pks))
        ]

    # ───────────────────────────────────────────────────────────── table API

    def get_table_data(self):
        """Data + column X positions for the table.

        Bug C1 fix: ``col_x`` is PK-based.
        Bug C2 fix: ``cote_proj`` recomputed via ``v_align.get_z(pk)``.
        """
        profile_nos = [f"P{i + 1}" for i in range(len(self.vert_pks))]
        lengths = [f"{l:.3f}" if i > 0 else "-"
                   for i, l in enumerate(self.seg_lengths)]
        pks = [f"{pk:.3f}" for pk in self.vert_pks]
        cote_tn = [f"{z:.3f}" for z in self.vert_ground_z]
        cote_proj = [f"{self.v_align.get_z(pk):.3f}"   # C2
                     for pk in self.vert_pks]
        col_x = self.pk_axis_x                          # C1
        diffs = self.vert_proj_z - self.vert_ground_z
        return profile_nos, lengths, pks, cote_tn, cote_proj, col_x, diffs


# ─────────────────────────────────────────────────────────────────────────────
# Top-level facade — what the CLI and Streamlit UI both call
# ─────────────────────────────────────────────────────────────────────────────

def build_design(
    cfg: DesignConfig,
    axe_path: Union[str, Path],
    terrain_path: Union[str, Path],
    out_dir: Union[str, Path],
) -> dict:
    """Build a full design and write DXF + XLSX into ``out_dir``.

    Returns a dict with paths to the generated artifacts.
    """
    from .cubature import compute_cubatures
    from .dxf_export import write_dxf
    from .excel_export import write_xlsx

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    design = RoadDesign(terrain_path, axe_path, cfg)
    design.cubatures = compute_cubatures(design)

    dxf_path = out_dir / cfg.dxf_filename
    xlsx_path = out_dir / cfg.xlsx_filename

    write_dxf(design, dxf_path)
    write_xlsx(design, xlsx_path)

    return {
        "dxf": dxf_path,
        "xlsx": xlsx_path,
        "warnings": design.tangent_warnings,
    }
