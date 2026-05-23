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
    "BRUCKNER":       6,   # mass-haul curve
    "BRUCKNER_BASE":  7,   # baseline + frame
    "BRUCKNER_TEXT":  7,   # labels
    # Step 7 — Profils en travers
    "PT_TN":          3,   # green TN line
    "PT_PROJET":      1,   # red projet (chaussée + accotement + fossé + talus)
    "PT_CUT_HATCH":   1,   # déblai polygons
    "PT_FILL_HATCH":  3,   # remblai polygons
    "PT_FRAME":       7,   # frame + axes
    "PT_TEXT":        7,   # labels & cotation
    "PT_AXIS":        5,   # vertical axis tick at t=0
    # Step 8 — Cartouche
    "CARTOUCHE":      7,
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
    _draw_bruckner(msp, design)      # Step 5 — mass-haul diagram
    _draw_cross_sections(doc, design)  # Step 7 — paperspace PT_01..PT_M
    _draw_plan_layouts(doc, design)    # Step 8 — paperspace PLAN_01..PLAN_N

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


# ─────────────────────────────────────────────────────────────────────────────
# Step 5: Diagramme de Bruckner (mass-haul) — drawn under the curvature row
# ─────────────────────────────────────────────────────────────────────────────

def _draw_bruckner(msp, design: "RoadDesign"):
    """Draw the mass-haul curve M(PK) = Σ(V_rem − V_deb) below the table.

    Same PK X-axis as profile + table (C1 contract). Vertical leaders
    highlight the local extrema (the natural haul-boundary points).
    """
    cub = design.cubatures
    if cub is None:
        return

    cfg = design.cfg

    # Vertical position: under the curvature diagram (which itself is right
    # under the table). We reproduce the same Y math without coupling.
    _, _, _, _, _, profile_base_y = design.get_profile_data()
    table_top = profile_base_y - 5.0
    table_bottom = table_top - sum(ROW_HEIGHTS)
    diag_top = table_bottom
    diag_bottom = diag_top - CURV_DIAG_ROW_HEIGHT

    y_top = diag_bottom - 4.0
    y_bot = y_top - cfg.bruckner_row_height
    y_zero = (y_top + y_bot) / 2     # baseline at M=0

    col_x = design.pk_axis_x
    x_min = float(col_x.min()) - 10.0
    x_max = float(col_x.max()) + 10.0

    # ── frame
    msp.add_line(Vec2(x_min, y_top), Vec2(x_max, y_top),
                 dxfattribs={"layer": "BRUCKNER_BASE"})
    msp.add_line(Vec2(x_min, y_bot), Vec2(x_max, y_bot),
                 dxfattribs={"layer": "BRUCKNER_BASE"})
    msp.add_line(Vec2(x_min, y_top), Vec2(x_min, y_bot),
                 dxfattribs={"layer": "BRUCKNER_BASE"})
    msp.add_line(Vec2(x_max, y_top), Vec2(x_max, y_bot),
                 dxfattribs={"layer": "BRUCKNER_BASE"})

    # ── baseline (M = 0)
    msp.add_line(Vec2(x_min, y_zero), Vec2(x_max, y_zero),
                 dxfattribs={"layer": "BRUCKNER_BASE", "linetype": "CENTER"})

    # ── title to the left of the frame
    title_width = 35.0
    x_title = x_min - title_width
    msp.add_line(Vec2(x_title, y_top), Vec2(x_title, y_bot),
                 dxfattribs={"layer": "BRUCKNER_BASE"})
    msp.add_line(Vec2(x_title, y_top), Vec2(x_min, y_top),
                 dxfattribs={"layer": "BRUCKNER_BASE"})
    msp.add_line(Vec2(x_title, y_bot), Vec2(x_min, y_bot),
                 dxfattribs={"layer": "BRUCKNER_BASE"})
    msp.add_text(
        "Diagramme de Bruckner", height=1.8,
        dxfattribs={"layer": "BRUCKNER_TEXT"},
    ).set_placement(
        Vec2(x_title + 1, y_zero + 1.0),
        align=TextEntityAlignment.MIDDLE_LEFT,
    )
    msp.add_text(
        f"({cfg.bruckner_v_scale:.4f} m / m³)", height=1.2,
        dxfattribs={"layer": "BRUCKNER_TEXT"},
    ).set_placement(
        Vec2(x_title + 1, y_zero - 1.5),
        align=TextEntityAlignment.MIDDLE_LEFT,
    )

    # ── curve, clipped to the frame so a runaway mass-haul doesn't escape
    half_height = cfg.bruckner_row_height / 2 - 1.0
    pts = []
    for x, m in zip(col_x, cub.bruckner):
        dy = m * cfg.bruckner_v_scale
        # clip
        if dy > half_height:
            dy = half_height
        elif dy < -half_height:
            dy = -half_height
        pts.append(Vec2(float(x), float(y_zero + dy)))
    msp.add_lwpolyline(pts, dxfattribs={"layer": "BRUCKNER"})

    # ── annotate extrema (local max/min of M)
    M = cub.bruckner
    n = len(M)
    extrema_idx: list[int] = []
    for i in range(1, n - 1):
        if (M[i] >= M[i - 1] and M[i] >= M[i + 1] and M[i] != M[i - 1]) or \
           (M[i] <= M[i - 1] and M[i] <= M[i + 1] and M[i] != M[i - 1]):
            extrema_idx.append(i)
    # Always include the endpoints
    extrema_idx = [0] + extrema_idx + [n - 1]

    for i in extrema_idx:
        x = float(col_x[i])
        dy = M[i] * cfg.bruckner_v_scale
        dy = max(min(dy, half_height), -half_height)
        y_pt = y_zero + dy
        # vertical leader to the baseline
        msp.add_line(Vec2(x, y_zero), Vec2(x, y_pt),
                     dxfattribs={"layer": "BRUCKNER",
                                 "linetype": "DASHED"})
        msp.add_text(
            f"{M[i]:+.0f} m³", height=1.3,
            dxfattribs={"layer": "BRUCKNER_TEXT"},
        ).set_placement(
            Vec2(x, y_pt + (1.0 if dy >= 0 else -1.5)),
            align=TextEntityAlignment.MIDDLE_CENTER,
        )

    # ── global total on the right
    x_tot = x_max + 3.0
    msp.add_text(
        f"M(fin) = {cub.balance:+.1f} m³", height=1.6,
        dxfattribs={"layer": "BRUCKNER_TEXT"},
    ).set_placement(Vec2(x_tot, y_zero + 1.5),
                    align=TextEntityAlignment.MIDDLE_LEFT)
    msp.add_text(
        ("Excédent → évacuer" if cub.balance < 0
         else "Déficit → emprunter"), height=1.4,
        dxfattribs={"layer": "BRUCKNER_TEXT"},
    ).set_placement(Vec2(x_tot, y_zero - 1.5),
                    align=TextEntityAlignment.MIDDLE_LEFT)


# ─────────────────────────────────────────────────────────────────────────────
# Step 7 — Profils en travers (paperspace layouts PT_01..PT_M)
# ─────────────────────────────────────────────────────────────────────────────

# A4 portrait in mm — Streamlit-Cloud-friendly when rendered to PDF
PT_PAGE_W_MM = 210.0
PT_PAGE_H_MM = 297.0


def _draw_cross_sections(doc, design: "RoadDesign"):
    """Build one A4 paperspace layout per cross-section.

    Lazy import to keep ``dxf_export`` usable even before Step 7 lands.
    """
    from .cross_section import all_sections

    sections = all_sections(design)
    if not sections:
        return

    # Attach cut/fill areas back onto the design so Step 7b can swap them
    # into cubature.py without changing call sites.
    design.section_areas = {
        s.pk: (s.cut_area, s.fill_area) for s in sections
    }

    for k, sec in enumerate(sections, start=1):
        name = f"PT_{k:03d}"
        if name in doc.layouts:
            doc.layouts.delete(name)
        lay = doc.layouts.new(name)
        lay.page_setup(
            size=(PT_PAGE_W_MM, PT_PAGE_H_MM),
            margins=(10, 10, 10, 10),
            units="mm",
            scale=1,
        )
        _draw_one_pt(lay, design, sec, page_index=k, n_total=len(sections))


def _draw_one_pt(lay, design: "RoadDesign", sec, page_index: int, n_total: int):
    """Draw a single cross-section page in its paperspace layout."""
    cfg = design.cfg
    # The paperspace coordinate system is in mm. Layout the page:
    #   ┌─ frame ──────────────────────────────────────────┐
    #   │ Title:  Profil en travers n° PT_xx  —  PK = …    │
    #   │ Cote projet axe = …   Cote TN axe = …            │
    #   │                                                    │
    #   │            (drawing area)                          │
    #   │                                                    │
    #   │  Bilan : Cut = … m²    Fill = … m²                 │
    #   └────────────────────────────────────────────────────┘

    margin = 12.0
    title_h = 18.0
    footer_h = 10.0
    draw_x0 = margin
    draw_y0 = margin + footer_h
    draw_x1 = PT_PAGE_W_MM - margin
    draw_y1 = PT_PAGE_H_MM - margin - title_h
    draw_w = draw_x1 - draw_x0
    draw_h = draw_y1 - draw_y0

    # Frame
    lay.add_lwpolyline(
        [(margin, margin), (PT_PAGE_W_MM - margin, margin),
         (PT_PAGE_W_MM - margin, PT_PAGE_H_MM - margin),
         (margin, PT_PAGE_H_MM - margin), (margin, margin)],
        close=True, dxfattribs={"layer": "PT_FRAME"},
    )
    # Title block separator
    lay.add_line(
        Vec2(margin, PT_PAGE_H_MM - margin - title_h),
        Vec2(PT_PAGE_W_MM - margin, PT_PAGE_H_MM - margin - title_h),
        dxfattribs={"layer": "PT_FRAME"},
    )
    # Footer separator
    lay.add_line(
        Vec2(margin, margin + footer_h),
        Vec2(PT_PAGE_W_MM - margin, margin + footer_h),
        dxfattribs={"layer": "PT_FRAME"},
    )

    # Title
    lay.add_text(
        f"Profil en travers PT_{page_index:03d}  —  PK = {sec.pk:.3f} m  "
        f"(page {page_index}/{n_total})",
        height=3.5, dxfattribs={"layer": "PT_TEXT"},
    ).set_placement(
        Vec2((margin + PT_PAGE_W_MM - margin) / 2,
             PT_PAGE_H_MM - margin - title_h / 2 + 2.5),
        align=TextEntityAlignment.MIDDLE_CENTER,
    )
    lay.add_text(
        f"Cote projet (axe) = {sec.z_axis_proj:.3f}     "
        f"Cote TN (axe) = {sec.z_axis_tn:.3f}     "
        f"Différence h = {sec.z_axis_proj - sec.z_axis_tn:+.3f} m",
        height=2.5, dxfattribs={"layer": "PT_TEXT"},
    ).set_placement(
        Vec2((margin + PT_PAGE_W_MM - margin) / 2,
             PT_PAGE_H_MM - margin - title_h / 2 - 2.5),
        align=TextEntityAlignment.MIDDLE_CENTER,
    )

    # Footer — areas
    lay.add_text(
        f"Aire déblai (cut)  = {sec.cut_area:>7.2f} m²    "
        f"Aire remblai (fill) = {sec.fill_area:>7.2f} m²",
        height=2.5, dxfattribs={"layer": "PT_TEXT"},
    ).set_placement(
        Vec2((margin + PT_PAGE_W_MM - margin) / 2, margin + footer_h / 2),
        align=TextEntityAlignment.MIDDLE_CENTER,
    )

    # ── data scaling: fit (TN + projet) bounding box into draw area
    all_pts = list(sec.tn_polyline) + list(sec.proj_polyline)
    ts = np.array([p[0] for p in all_pts])
    zs = np.array([p[1] for p in all_pts])
    t_min, t_max = float(ts.min()), float(ts.max())
    z_min, z_max = float(zs.min()), float(zs.max())
    # 5 % margin
    span_t = max(0.1, t_max - t_min)
    span_z = max(0.1, z_max - z_min)
    sx = (draw_w * 0.92) / span_t                  # mm per metre H
    sy = (draw_h * 0.88) / span_z                  # mm per metre V
    s = min(sx, sy)                                # uniform scale (≈ 1:100 or so)
    cx = draw_x0 + draw_w / 2
    cy = draw_y0 + draw_h / 2
    t_mid = (t_min + t_max) / 2
    z_mid = (z_min + z_max) / 2

    def xy(t, z):
        return ((t - t_mid) * s + cx, (z - z_mid) * s + cy)

    # ── hatched cut / fill polygons
    for poly in sec.fill_polygons:
        if len(poly) >= 3:
            h = lay.add_hatch(color=3, dxfattribs={"layer": "PT_FILL_HATCH"})
            h.paths.add_polyline_path(
                [xy(t, z) for t, z in poly], is_closed=True,
            )
            h.set_pattern_fill("ANSI31", scale=0.5, color=3)
    for poly in sec.cut_polygons:
        if len(poly) >= 3:
            h = lay.add_hatch(color=1, dxfattribs={"layer": "PT_CUT_HATCH"})
            h.paths.add_polyline_path(
                [xy(t, z) for t, z in poly], is_closed=True,
            )
            h.set_pattern_fill("ANSI31", scale=0.5, color=1)

    # ── TN line
    lay.add_lwpolyline(
        [xy(t, z) for t, z in sec.tn_polyline],
        dxfattribs={"layer": "PT_TN"},
    )
    # ── Projet line
    lay.add_lwpolyline(
        [xy(t, z) for t, z in sec.proj_polyline],
        dxfattribs={"layer": "PT_PROJET"},
    )

    # ── Axis tick at t = 0
    x_ax, _ = xy(0.0, z_mid)
    lay.add_line(Vec2(x_ax, draw_y0), Vec2(x_ax, draw_y1),
                 dxfattribs={"layer": "PT_AXIS", "linetype": "CENTER"})
    lay.add_text(
        "Axe", height=2.0, dxfattribs={"layer": "PT_AXIS"},
    ).set_placement(Vec2(x_ax + 1.5, draw_y1 - 3),
                    align=TextEntityAlignment.MIDDLE_LEFT)

    # ── Break-point labels along the projet polyline
    for t, z, label in sec.projet_break_points:
        if label == "axe":
            continue
        bx, by = xy(t, z)
        lay.add_circle(Vec2(bx, by), radius=0.6,
                       dxfattribs={"layer": "PT_PROJET"})
        lay.add_text(
            label, height=1.6, dxfattribs={"layer": "PT_TEXT"},
        ).set_placement(Vec2(bx, by - 2.0),
                        align=TextEntityAlignment.MIDDLE_CENTER)

    # ── Scale legend
    lay.add_text(
        f"Échelle  H 1:{int(round(1000 / s))}  "
        f"V 1:{int(round(1000 / s))}",
        height=2.0, dxfattribs={"layer": "PT_TEXT"},
    ).set_placement(
        Vec2(PT_PAGE_W_MM - margin - 2, margin + footer_h + 2),
        align=TextEntityAlignment.RIGHT,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Step 8 — Cartouche + multi-A1 plan paperspace (PLAN_01..PLAN_N)
# ─────────────────────────────────────────────────────────────────────────────

# A1 landscape in mm
A1_W_MM = 841.0
A1_H_MM = 594.0


def _ensure_cartouche_block(doc):
    """Define the reusable CARTOUCHE block once per document."""
    if "CARTOUCHE" in doc.blocks:
        return doc.blocks.get("CARTOUCHE")
    blk = doc.blocks.new(name="CARTOUCHE")

    w, h = 180.0, 100.0   # mm
    blk.add_lwpolyline(
        [(0, 0), (w, 0), (w, h), (0, h), (0, 0)],
        close=True, dxfattribs={"layer": "CARTOUCHE"},
    )

    # Inner cells
    rows = [0.0, 14.0, 28.0, 44.0, 60.0, 76.0, 88.0, h]
    for y in rows[1:-1]:
        blk.add_line(Vec2(0, y), Vec2(w, y),
                     dxfattribs={"layer": "CARTOUCHE"})
    blk.add_line(Vec2(40, rows[1]), Vec2(40, rows[2]),
                 dxfattribs={"layer": "CARTOUCHE"})
    blk.add_line(Vec2(90, rows[1]), Vec2(90, rows[2]),
                 dxfattribs={"layer": "CARTOUCHE"})
    blk.add_line(Vec2(140, rows[1]), Vec2(140, rows[2]),
                 dxfattribs={"layer": "CARTOUCHE"})

    # Static labels (these don't change per sheet)
    labels = [
        (5, rows[6] + 8, "PROJET"),
        (5, rows[5] + 8, "MAITRE D'OUVRAGE"),
        (5, rows[4] + 8, "BUREAU D'ÉTUDES (BET)"),
        (5, rows[3] + 8, "INDICATIONS"),
        (5, rows[2] + 8, "PLAN"),
        (5,  rows[1] + 8, "ÉCHELLES / DATES"),
        (5,  rows[1] + 2, "Échelle H:"),
        (45, rows[1] + 2, "Échelle V:"),
        (95, rows[1] + 2, "Date:"),
        (145, rows[1] + 2, "Indice:"),
    ]
    for x, y, t in labels:
        blk.add_text(
            t, height=2.4,
            dxfattribs={"layer": "CARTOUCHE", "color": 7},
        ).set_placement(Vec2(x, y), align=TextEntityAlignment.LEFT)

    # Dynamic ATTDEFs — filled per layout insertion via INSERT.attribs
    attdefs = [
        ("PROJET",        Vec2(5,  rows[6] + 3), 3.5),
        ("MAITRE_OUV",    Vec2(5,  rows[5] + 3), 2.8),
        ("BET",           Vec2(5,  rows[4] + 3), 2.8),
        ("DESIGNER",      Vec2(95, rows[4] + 3), 2.8),
        ("PLAN_N",        Vec2(95, rows[3] + 3), 3.5),
        ("PK_RANGE",      Vec2(5,  rows[3] + 3), 2.8),
        ("INDICE_TXT",    Vec2(160, rows[1] + 7), 4.0),
        ("DATE_TXT",      Vec2(110, rows[1] + 7), 2.8),
        ("ECH_H",         Vec2(20, rows[1] + 7), 2.8),
        ("ECH_V",         Vec2(60, rows[1] + 7), 2.8),
    ]
    for tag, pos, height in attdefs:
        blk.add_attdef(
            tag=tag, text="",
            insert=pos, height=height,
            dxfattribs={"layer": "CARTOUCHE"},
        )
    return blk


def _draw_plan_layouts(doc, design: "RoadDesign"):
    """Create PLAN_01..PLAN_N — one A1 sheet per ``sheet_length_pk`` window.

    Each sheet contains:
      • A modelspace viewport zoomed to the plan window
      • A modelspace viewport zoomed to the profile/table window
      • A CARTOUCHE block instance with attribs filled
    """
    cfg = design.cfg
    _ensure_cartouche_block(doc)

    pk_min = float(design.vert_pks.min())
    pk_max = float(design.vert_pks.max())
    n_sheets = max(1, int(np.ceil((pk_max - pk_min) / cfg.sheet_length_pk)))

    for k in range(n_sheets):
        pk_start = pk_min + k * cfg.sheet_length_pk
        pk_end = min(pk_max, pk_start + cfg.sheet_length_pk)
        name = f"PLAN_{k + 1:02d}"
        if name in doc.layouts:
            doc.layouts.delete(name)
        lay = doc.layouts.new(name)
        lay.page_setup(
            size=(A1_W_MM, A1_H_MM),
            margins=(10, 10, 10, 10),
            units="mm",
            scale=1,
        )

        # Outer frame
        lay.add_lwpolyline(
            [(10, 10), (A1_W_MM - 10, 10),
             (A1_W_MM - 10, A1_H_MM - 10), (10, A1_H_MM - 10), (10, 10)],
            close=True, dxfattribs={"layer": "CARTOUCHE"},
        )

        # Viewport 1: plan view of this PK window
        _add_plan_viewport(lay, design, pk_start, pk_end)
        # Viewport 2: profile + table of this PK window
        _add_profile_viewport(lay, design, pk_start, pk_end)

        # Insert cartouche bottom-right
        cart_x = A1_W_MM - 10 - 180.0 - 6.0
        cart_y = 10 + 6.0
        ref = lay.add_blockref("CARTOUCHE", insert=Vec2(cart_x, cart_y))
        ref.add_auto_attribs({
            "PROJET":        cfg.cartouche.projet or "—",
            "MAITRE_OUV":    cfg.cartouche.maitre_ouvrage or "—",
            "BET":           cfg.cartouche.bet or "—",
            "DESIGNER":      cfg.cartouche.designer or "—",
            "PLAN_N":        f"{cfg.cartouche.plan_n or 'PLAN'}-{k + 1:02d}",
            "PK_RANGE":      f"PK {pk_start:.1f} → {pk_end:.1f}",
            "INDICE_TXT":    cfg.cartouche.indice,
            "DATE_TXT":      cfg.cartouche.date or "—",
            "ECH_H":         cfg.cartouche.echelle_h,
            "ECH_V":         cfg.cartouche.echelle_v,
        })


def _add_plan_viewport(lay, design, pk_start: float, pk_end: float):
    """Add a paperspace viewport showing the rotated plan over [pk_start, pk_end]."""
    # Find rotated-X bounds for this PK window
    pk_grid = np.linspace(pk_start, pk_end, 50)
    x_rot = [design.pk_to_x_rot(pk) for pk in pk_grid]
    x_min, x_max = min(x_rot), max(x_rot)
    # Plan y range = vert_y_rot envelope ± edges
    y_min = float(design.vert_y_rot.min()) - 30.0
    y_max = float(design.vert_y_rot.max()) + 30.0
    cx, cy = (x_min + x_max) / 2, (y_min + y_max) / 2
    view_h = max(y_max - y_min, (x_max - x_min) * (200 / 600))

    # Viewport position on the sheet (top half)
    vp = lay.add_viewport(
        center=(A1_W_MM / 2, A1_H_MM * 0.70),
        size=(A1_W_MM - 40, A1_H_MM * 0.45),
        view_center_point=(cx, cy),
        view_height=view_h,
    )
    vp.dxf.status = 1
    return vp


def _add_profile_viewport(lay, design, pk_start: float, pk_end: float):
    """Add a paperspace viewport showing the profile + table over the PK window."""
    cfg = design.cfg
    x0 = design.pk_to_x(pk_start)
    x1 = design.pk_to_x(pk_end)
    # Y range covers from below the Bruckner row to above the profile baseline
    _, _, _, _, _, profile_base_y = design.get_profile_data()
    top = profile_base_y + 60.0
    bottom = (profile_base_y - 5.0
              - sum(ROW_HEIGHTS)
              - CURV_DIAG_ROW_HEIGHT
              - 4.0 - cfg.bruckner_row_height - 5.0)
    cx, cy = (x0 + x1) / 2, (top + bottom) / 2
    view_h = top - bottom

    vp = lay.add_viewport(
        center=(A1_W_MM / 2, A1_H_MM * 0.27),
        size=(A1_W_MM - 40, A1_H_MM * 0.42),
        view_center_point=(cx, cy),
        view_height=view_h,
    )
    vp.dxf.status = 1
    return vp
