"""DXF assembly — plan view, profil en long, tableau (7 rows), diagramme des
courbures, rappel lines. Cartouches and profils en travers land in later steps.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Union

import ezdxf
import numpy as np
from ezdxf.enums import TextEntityAlignment
from ezdxf.math import Vec2

from .geometry_engine import compute_normal, cutting_line_points

if TYPE_CHECKING:
    from .road_design import RoadDesign


# ─────────────────────────────────────────────────────────────────────────────
# Layer colours — single source of truth, mirrored in CLAUDE.md §6
# ─────────────────────────────────────────────────────────────────────────────

LAYERS = {
    "AXIS":           5,   # blue
    "EDGES":          8,   # grey
    "GROUND":         3,   # green
    "PROJECT":        1,   # red
    "RAPPEL":         2,   # yellow
    "HAUTEURS_REM":   3,   # green (Remb labels)
    "HAUTEURS_DEB":   1,   # red   (Déb labels)
    "TABLE":          7,
    "TABLE_TEXT":     7,
    "TABLE_CUBATURE": 6,   # 7th row text
    "BUBBLES":        4,   # cyan
    "CUTTING_LINES":  6,
    "TICKS":          6,
    "ARC_ARROW":      4,
    "STRAIGHT_ARROW": 4,
    "CURV_DIAG":      7,
    "CURV_DIAG_PROJ": 1,
    "CURV_DIAG_ARC":  4,
}


def _setup_layers(doc):
    """Pre-create all layers + the DASHED linetype needed by RAPPEL."""
    if "DASHED" not in doc.linetypes:
        doc.linetypes.new("DASHED", dxfattribs={
            "description": "Dashed",
            "pattern": "A,.5,-.25",
        })
    if "CENTER" not in doc.linetypes:
        doc.linetypes.new("CENTER", dxfattribs={
            "description": "Center line",
            "pattern": "A,1.25,-.25,.25,-.25",
        })
    for name, color in LAYERS.items():
        if name not in doc.layers:
            doc.layers.new(name, dxfattribs={"color": color})


# ─────────────────────────────────────────────────────────────────────────────
# Top-level entry
# ─────────────────────────────────────────────────────────────────────────────

def write_dxf(design: "RoadDesign", out_path: Union[str, Path]) -> Path:
    """Build the complete DXF (plan + profile + table + curvature diagram)."""
    doc = ezdxf.new("R2010", setup=True)
    _setup_layers(doc)
    msp = doc.modelspace()

    _draw_plan(msp, design)
    _draw_profile(msp, design)
    _draw_table(msp, design)         # includes the 7th cubature row

    out_path = Path(out_path)
    doc.saveas(out_path)
    print(f"DXF generated: {out_path}")
    return out_path


# ─────────────────────────────────────────────────────────────────────────────
# Plan view (rotated coordinates)
# ─────────────────────────────────────────────────────────────────────────────

def _draw_plan(msp, design: "RoadDesign"):
    cfg = design.cfg
    axis = design.get_plan_axis()
    left, right = design.get_plan_edges()

    msp.add_lwpolyline(
        [Vec2(x, y) for x, y in axis],
        dxfattribs={"layer": "AXIS"},
    )
    msp.add_lwpolyline(
        [Vec2(x, y) for x, y in left],
        dxfattribs={"layer": "EDGES"},
    )
    msp.add_lwpolyline(
        [Vec2(x, y) for x, y in right],
        dxfattribs={"layer": "EDGES"},
    )

    # Arc annotations — ticks + curved arrow
    for arc in design.get_arc_annotations():
        for endpoint_xy, tangent in (
            (arc["start_xy_rot"], arc["start_tangent_rot"]),
            (arc["end_xy_rot"], arc["end_tangent_rot"]),
        ):
            if endpoint_xy is None or tangent is None:
                continue
            x_rot, y_rot = endpoint_xy
            normal = np.array([-tangent[1], tangent[0]])
            p1 = np.array([x_rot, y_rot]) + normal * (cfg.tick_length / 2)
            p2 = np.array([x_rot, y_rot]) - normal * (cfg.tick_length / 2)
            msp.add_line(Vec2(p1[0], p1[1]), Vec2(p2[0], p2[1]),
                         dxfattribs={"layer": "TICKS"})
            tp = p1 + normal * cfg.tick_offset
            msp.add_text(
                f"R={arc['radius']:.3f}", height=2.0,
                dxfattribs={"layer": "TICKS"},
            ).set_placement(Vec2(tp[0], tp[1]), align=TextEntityAlignment.LEFT)

        msp.add_lwpolyline(
            [Vec2(x, y) for x, y in arc["arrow_points_rot"]],
            dxfattribs={"layer": "ARC_ARROW"},
        )
        msp.add_text(
            arc["label"], height=2.5, dxfattribs={"layer": "ARC_ARROW"},
        ).set_placement(
            Vec2(arc["midpoint_rot"][0], arc["midpoint_rot"][1]),
            align=TextEntityAlignment.MIDDLE_CENTER,
        )

    # Straight-segment length labels
    for line in design.get_line_annotations():
        seg = line["offset_line_rot"]
        msp.add_line(Vec2(seg[0, 0], seg[0, 1]),
                     Vec2(seg[1, 0], seg[1, 1]),
                     dxfattribs={"layer": "STRAIGHT_ARROW"})
        msp.add_text(
            line["label"], height=2.5,
            dxfattribs={"layer": "STRAIGHT_ARROW"},
        ).set_placement(
            Vec2(line["midpoint_rot"][0], line["midpoint_rot"][1]),
            align=TextEntityAlignment.MIDDLE_CENTER,
        )

    # Cutting lines + bubbles at each station vertex
    for i, (x_rot, y_rot) in enumerate(zip(design.vert_x_rot, design.vert_y_rot)):
        if i == 0:
            dx = design.vert_x_rot[i + 1] - x_rot
            dy = design.vert_y_rot[i + 1] - y_rot
        elif i == len(design.vert_x_rot) - 1:
            dx = x_rot - design.vert_x_rot[i - 1]
            dy = y_rot - design.vert_y_rot[i - 1]
        else:
            dx = design.vert_x_rot[i + 1] - design.vert_x_rot[i - 1]
            dy = design.vert_y_rot[i + 1] - design.vert_y_rot[i - 1]
        normal = compute_normal(dx, dy)
        p1, p2 = cutting_line_points(
            np.array([x_rot, y_rot]), normal, cfg.cutting_line_length
        )
        msp.add_line(Vec2(p1[0], p1[1]), Vec2(p2[0], p2[1]),
                     dxfattribs={"layer": "CUTTING_LINES"})
        bubble = np.array([x_rot, y_rot]) + normal * cfg.annotation_offset
        msp.add_circle(center=Vec2(bubble[0], bubble[1]), radius=2.0,
                       dxfattribs={"layer": "BUBBLES"})
        msp.add_text(
            f"P{i + 1}", height=2.0, dxfattribs={"layer": "BUBBLES"},
        ).set_placement(Vec2(bubble[0], bubble[1]),
                        align=TextEntityAlignment.MIDDLE_CENTER)


# ─────────────────────────────────────────────────────────────────────────────
# Profile (PK-based X)
# ─────────────────────────────────────────────────────────────────────────────

def _draw_profile(msp, design: "RoadDesign"):
    cfg = design.cfg
    (prof_x, ground_y, proj_y,
     prof_x_dense, proj_y_dense, profile_base_y) = design.get_profile_data()

    msp.add_lwpolyline(
        [Vec2(x, y) for x, y in zip(prof_x, ground_y)],
        dxfattribs={"layer": "GROUND"},
    )
    msp.add_lwpolyline(
        [Vec2(x, y) for x, y in zip(prof_x_dense, proj_y_dense)],
        dxfattribs={"layer": "PROJECT"},
    )

    # Rappel lines: slanted (C1 fix — plan X ≠ profile X anymore)
    for (x_plan, y_plan), (x_prof, y_prof) in design.get_rappel_segments():
        msp.add_line(
            Vec2(x_plan, y_plan), Vec2(x_prof, y_prof),
            dxfattribs={"layer": "RAPPEL", "linetype": "DASHED"},
        )

    # Cut/Fill labels at each vertex (Remb in green, Déb in red)
    cub = design.cubatures
    h = cub.h_per_vertex if cub is not None else (
        design.vert_proj_z - design.vert_ground_z
    )
    for i, h_val in enumerate(h):
        if abs(h_val) < 0.01:
            continue
        label = f"{'Remb' if h_val > 0 else 'Déb'}={abs(h_val):.2f}m"
        layer = "HAUTEURS_REM" if h_val > 0 else "HAUTEURS_DEB"
        x_pos = prof_x[i]
        y_proj = profile_base_y + (design.vert_proj_z[i] - design.datum) * cfg.v_scale
        txt = msp.add_text(label, height=1.5, dxfattribs={"layer": layer})
        txt.set_placement(
            Vec2(x_pos + 0.5, y_proj + 0.5),
            align=TextEntityAlignment.MIDDLE_CENTER,
        )
        txt.dxf.rotation = 45


# ─────────────────────────────────────────────────────────────────────────────
# Table (now 7 rows) + curvature diagram
# ─────────────────────────────────────────────────────────────────────────────

# Row layout: top to bottom
ROW_LABELS = [
    "Numéro du Profil",
    "Distances Partielles",
    "Distances Cumulées (PK)",
    "Cotes TN",
    "Cotes Projet",
    "Pentes et Rampes",
    "Cubatures Déb. / Remb. (m³)",  # Step 3 — new row
]
ROW_HEIGHTS = [5.0, 5.0, 15.0, 15.0, 15.0, 8.0, 12.0]   # 7 rows
CURV_DIAG_ROW_HEIGHT = 8.0


def _draw_table(msp, design: "RoadDesign"):
    """Draw the 7-row table and the curvature diagram below it."""
    cfg = design.cfg
    cub = design.cubatures

    (profile_nos, lengths, pks, cote_tn, cote_proj,
     col_x, diffs) = design.get_table_data()
    _, _, _, _, _, profile_base_y = design.get_profile_data()

    table_top = profile_base_y - 5.0
    margin = 10.0
    x_min = float(min(col_x)) - margin
    x_max = float(max(col_x)) + margin

    # Row Y positions (top of each row)
    row_y = [table_top]
    y = table_top
    for h in ROW_HEIGHTS:
        y -= h
        row_y.append(y)
    table_bottom = row_y[-1]
    y_diag_top = table_bottom
    y_diag_bottom = y_diag_top - CURV_DIAG_ROW_HEIGHT

    # ── frame
    msp.add_line(Vec2(x_min, table_top), Vec2(x_min, y_diag_bottom),
                 dxfattribs={"layer": "TABLE"})
    msp.add_line(Vec2(x_max, table_top), Vec2(x_max, y_diag_bottom),
                 dxfattribs={"layer": "TABLE"})
    for cx in col_x:
        msp.add_line(Vec2(cx, table_top), Vec2(cx, table_bottom),
                     dxfattribs={"layer": "TABLE"})
    for ry in row_y:
        msp.add_line(Vec2(x_min, ry), Vec2(x_max, ry),
                     dxfattribs={"layer": "TABLE"})
    msp.add_line(Vec2(x_min, y_diag_bottom), Vec2(x_max, y_diag_bottom),
                 dxfattribs={"layer": "TABLE"})

    # ── title column on the left
    title_width = 35.0
    x_title = x_min - title_width
    msp.add_line(Vec2(x_title, table_top), Vec2(x_title, y_diag_bottom),
                 dxfattribs={"layer": "TABLE"})
    for i, label in enumerate(ROW_LABELS):
        y_row_top = row_y[i]
        y_row_bot = row_y[i + 1]
        msp.add_line(Vec2(x_title, y_row_top), Vec2(x_min, y_row_top),
                     dxfattribs={"layer": "TABLE"})
        msp.add_text(
            label, height=1.8, dxfattribs={"layer": "TABLE_TEXT"},
        ).set_placement(
            Vec2(x_title + 1, (y_row_top + y_row_bot) / 2),
            align=TextEntityAlignment.MIDDLE_LEFT,
        )
    # Diagram row title
    msp.add_text(
        "Diagramme des Courbures", height=1.8,
        dxfattribs={"layer": "TABLE_TEXT"},
    ).set_placement(
        Vec2(x_title + 1, (y_diag_top + y_diag_bottom) / 2),
        align=TextEntityAlignment.MIDDLE_LEFT,
    )

    # ── per-column cell contents
    n = len(col_x)
    for i in range(n):
        x_pos = col_x[i]

        # 0 — Profile number
        msp.add_text(
            profile_nos[i], height=3.0,
            dxfattribs={"layer": "TABLE_TEXT"},
        ).set_placement(
            Vec2(x_pos, row_y[0] - 2.5),
            align=TextEntityAlignment.MIDDLE_CENTER,
        )

        # 1 — Distance partielle (placed mid-block, like the original)
        if i < n - 1:
            mid_x = (x_pos + col_x[i + 1]) / 2
            seg_len = lengths[i + 1]
            msp.add_text(
                seg_len, height=2.5,
                dxfattribs={"layer": "TABLE_TEXT"},
            ).set_placement(
                Vec2(mid_x, row_y[1] - 2.5),
                align=TextEntityAlignment.MIDDLE_CENTER,
            )

        # 2 — PK (vertical)
        t = msp.add_text(pks[i], height=1.8,
                         dxfattribs={"layer": "TABLE_TEXT"})
        t.set_placement(Vec2(x_pos + 1, row_y[2] - 7.5),
                        align=TextEntityAlignment.MIDDLE_CENTER)
        t.dxf.rotation = 90

        # 3 — Cote TN (vertical)
        t = msp.add_text(cote_tn[i], height=1.8,
                         dxfattribs={"layer": "TABLE_TEXT"})
        t.set_placement(Vec2(x_pos + 0.6, row_y[3] - 7.5),
                        align=TextEntityAlignment.MIDDLE_CENTER)
        t.dxf.rotation = 90

        # 4 — Cote Projet (vertical, recomputed via v_align.get_z — C2)
        t = msp.add_text(cote_proj[i], height=1.8,
                         dxfattribs={"layer": "TABLE_TEXT"})
        t.set_placement(Vec2(x_pos + 0.6, row_y[4] - 7.5),
                        align=TextEntityAlignment.MIDDLE_CENTER)
        t.dxf.rotation = 90

        # 6 — Cubatures (Step 3 — new) — stacked Déb / Remb per segment.
        # We place the values in the i-th column but they describe the
        # segment ENDING at vertex i (i.e. between i-1 and i).
        if cub is not None and i > 0:
            mid_x = (col_x[i - 1] + col_x[i]) / 2
            v_deb = cub.V_deb_per_seg[i - 1]
            v_rem = cub.V_rem_per_seg[i - 1]
            y_top = row_y[6] - 3.0
            y_bot = row_y[6] - 8.0
            if v_deb > 0.5:
                msp.add_text(
                    f"D {v_deb:.0f}", height=1.6,
                    dxfattribs={"layer": "TABLE_CUBATURE", "color": 1},
                ).set_placement(
                    Vec2(mid_x, y_top),
                    align=TextEntityAlignment.MIDDLE_CENTER,
                )
            if v_rem > 0.5:
                msp.add_text(
                    f"R {v_rem:.0f}", height=1.6,
                    dxfattribs={"layer": "TABLE_CUBATURE", "color": 3},
                ).set_placement(
                    Vec2(mid_x, y_bot),
                    align=TextEntityAlignment.MIDDLE_CENTER,
                )

    # ── Row 5: Pentes et Rampes (Diagramme des Courbures style)
    _draw_grade_diagram(msp, design, col_x, row_y[5], row_y[6])

    # ── Row 7+ : curvature diagram below the table
    _draw_curvature_diagram(msp, design, col_x, y_diag_top, y_diag_bottom)

    # ── Totals box on the right of the cubature row
    if cub is not None:
        x_tot = x_max + 3.0
        y_tot_top = row_y[6]
        msp.add_text(
            f"Σ Déblai  = {cub.total_deb:>9.1f} m³", height=1.6,
            dxfattribs={"layer": "TABLE_CUBATURE", "color": 1},
        ).set_placement(Vec2(x_tot, y_tot_top - 3.0),
                        align=TextEntityAlignment.MIDDLE_LEFT)
        msp.add_text(
            f"Σ Remblai = {cub.total_rem:>9.1f} m³", height=1.6,
            dxfattribs={"layer": "TABLE_CUBATURE", "color": 3},
        ).set_placement(Vec2(x_tot, y_tot_top - 6.0),
                        align=TextEntityAlignment.MIDDLE_LEFT)
        msp.add_text(
            f"Bilan      = {cub.balance:>+9.1f} m³", height=1.6,
            dxfattribs={"layer": "TABLE_CUBATURE", "color": 7},
        ).set_placement(Vec2(x_tot, y_tot_top - 9.0),
                        align=TextEntityAlignment.MIDDLE_LEFT)


# ─────────────────────────────────────────────────────────────────────────────
# Row 5: Pentes et rampes — sloped lines with P=…% L=…m labels
# ─────────────────────────────────────────────────────────────────────────────

def _draw_grade_diagram(msp, design: "RoadDesign", col_x,
                        y_row_top: float, y_row_bot: float):
    """Render the slope-and-length row (row 5) showing each tangent grade
    of the ligne rouge."""
    y_mid = (y_row_top + y_row_bot) / 2

    for grade, pvi_a, pvi_b in zip(
        design.v_align.grades,
        design.v_align.pvi[:-1],
        design.v_align.pvi[1:],
    ):
        s_x = design.pk_to_x(pvi_a[0])
        e_x = design.pk_to_x(pvi_b[0])
        length = pvi_b[0] - pvi_a[0]
        mid_x = (s_x + e_x) / 2
        y1 = y_row_bot + 1 if grade > 0 else y_row_top - 1
        y2 = y_row_top - 1 if grade > 0 else y_row_bot + 1
        msp.add_line(Vec2(s_x, y1), Vec2(e_x, y2),
                     dxfattribs={"layer": "CURV_DIAG_PROJ"})
        msp.add_text(
            f"P={grade * 100:.2f}%", height=1.4,
            dxfattribs={"layer": "CURV_DIAG"},
        ).set_placement(Vec2(mid_x, y_mid + 0.8),
                        align=TextEntityAlignment.MIDDLE_CENTER)
        msp.add_text(
            f"L={length:.2f}m", height=1.2,
            dxfattribs={"layer": "CURV_DIAG"},
        ).set_placement(Vec2(mid_x, y_mid - 1.8),
                        align=TextEntityAlignment.MIDDLE_CENTER)


# ─────────────────────────────────────────────────────────────────────────────
# Curvature diagram (row 7+) — bumps for each parabolic curve
# ─────────────────────────────────────────────────────────────────────────────

def _draw_curvature_diagram(msp, design: "RoadDesign", col_x,
                            y_top: float, y_bot: float):
    y_mid = (y_top + y_bot) / 2
    bump_amp = (y_top - y_bot) * 0.4
    msp.add_line(
        Vec2(float(min(col_x)) - 10, y_bot),
        Vec2(float(max(col_x)) + 10, y_bot),
        dxfattribs={"layer": "CURV_DIAG", "linetype": "CENTER"},
    )

    segments = _build_curvature_segments(design)
    for seg in segments:
        s_x = design.pk_to_x(seg["start"])
        e_x = design.pk_to_x(seg["end"])
        mid_x = (s_x + e_x) / 2
        length = seg["end"] - seg["start"]
        msp.add_line(Vec2(s_x, y_top), Vec2(s_x, y_bot),
                     dxfattribs={"layer": "CURV_DIAG"})
        msp.add_line(Vec2(e_x, y_top), Vec2(e_x, y_bot),
                     dxfattribs={"layer": "CURV_DIAG"})

        if seg["type"] == "STR":
            pente = seg["grade"]
            y1 = y_bot + 2 if pente > 0 else y_top - 2
            y2 = y_top - 2 if pente > 0 else y_bot + 2
            msp.add_line(Vec2(s_x, y1), Vec2(e_x, y2),
                         dxfattribs={"layer": "CURV_DIAG_PROJ"})
            msp.add_text(
                f"L={length:.2f}m", height=1.2,
                dxfattribs={"layer": "CURV_DIAG"},
            ).set_placement(Vec2(mid_x, y_mid),
                            align=TextEntityAlignment.MIDDLE_CENTER)
        else:
            is_sag = seg["sign"] > 0
            pts = []
            for t in np.linspace(0, 1, 12):
                cx = s_x + (e_x - s_x) * t
                h = 4 * t * (1 - t) * bump_amp
                cy = y_bot + h if not is_sag else y_top - h
                pts.append(Vec2(cx, cy))
            msp.add_lwpolyline(pts, dxfattribs={"layer": "CURV_DIAG_ARC"})
            label_y = (y_top + 1.5) if not is_sag else (y_bot - 2.5)
            msp.add_text(
                f"R={abs(seg['radius']):.0f}", height=1.5,
                dxfattribs={"layer": "CURV_DIAG_ARC"},
            ).set_placement(Vec2(mid_x, label_y),
                            align=TextEntityAlignment.MIDDLE_CENTER)
            msp.add_text(
                f"L={length:.2f}m", height=1.2,
                dxfattribs={"layer": "CURV_DIAG_ARC"},
            ).set_placement(Vec2(mid_x, y_mid),
                            align=TextEntityAlignment.MIDDLE_CENTER)


def _build_curvature_segments(design):
    """Walk tangent → curve → tangent → … from the v_align."""
    v = design.v_align
    segments = []
    last_pk = v.pvi[0, 0]
    for curve in v.curves:
        if curve["start"] > last_pk:
            segments.append({
                "type": "STR",
                "start": last_pk,
                "end": curve["start"],
                "grade": v.grades[curve["pvi_idx"] - 1],
            })
        segments.append({
            "type": "ARC",
            "start": curve["start"],
            "end": curve["end"],
            "radius": curve["R"],
            "sign": curve["sign"],
            "g1": curve["g1"],
            "g2": v.grades[curve["pvi_idx"]],
        })
        last_pk = curve["end"]
    final_pk = v.pvi[-1, 0]
    if last_pk < final_pk:
        segments.append({
            "type": "STR",
            "start": last_pk,
            "end": final_pk,
            "grade": v.grades[-1],
        })
    return segments
