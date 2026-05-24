"""Direct matplotlib PDF rendering — full DXF fidelity, true vector output.

Replaces the older ``pdf_export.py`` (which round-tripped through
``ezdxf.addons.drawing`` and lost text fidelity + was slow). This module
renders each page from the in-memory ``RoadDesign`` data using matplotlib's
native primitives, with **points-based font sizes** so labels stay readable
at any zoom level.

Two PDFs are produced, each prefixed with a cover page and a uniform
**company-name header** on every subsequent page:

  (a) ``plan_par_sections.pdf``  —  A1 landscape, one page per
      ``cfg.sheet_length_pk`` window of road. Each page shows the plan
      view on top and the profile + 7-row table + curvature diagram +
      Bruckner on the bottom — identical layout to the DXF modelspace,
      with all labels, dimensions, P=…% / R=… / L=… annotations.

  (b) ``profils_en_travers.pdf``  —  A4 portrait, one page per cross-
      section. The section is sized to fill the drawing area with
      independent H / V scales (typically H 1:500 V 1:100) chosen so
      both the lateral extent and the elevation range are clearly
      visible without distortion of the typical-section break points.

All output is vector (matplotlib's PDF backend), text remains selectable
where the OS PDF viewer supports it, and zoom is unlimited.
"""
from __future__ import annotations

import datetime as _dt
import io
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional, Sequence, Tuple, Union

import matplotlib
matplotlib.use("Agg")  # Streamlit-Cloud-safe (rule 9.3)

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import FancyBboxPatch, Polygon as MplPolygon, Rectangle

if TYPE_CHECKING:
    from .road_design import RoadDesign


# ─────────────────────────────────────────────────────────────────────────────
# Paper sizes (mm → inches)
# ─────────────────────────────────────────────────────────────────────────────

MM_PER_INCH = 25.4
A1_LANDSCAPE_IN: Tuple[float, float] = (841 / MM_PER_INCH, 594 / MM_PER_INCH)
A4_PORTRAIT_IN: Tuple[float, float] = (210 / MM_PER_INCH, 297 / MM_PER_INCH)
A3_PORTRAIT_IN: Tuple[float, float] = (297 / MM_PER_INCH, 420 / MM_PER_INCH)
# Cross-section pages use A3 portrait — the BET default for detail PTs.
PT_PAGE_IN: Tuple[float, float] = A3_PORTRAIT_IN
PT_PAGE_W_MM: float = 297.0
PT_PAGE_H_MM: float = 420.0


# ─────────────────────────────────────────────────────────────────────────────
# Professional company-name header — drawn on every page (not the cover)
# ─────────────────────────────────────────────────────────────────────────────

def _draw_company_header(
    fig: plt.Figure,
    design: "RoadDesign",
    page_title: str,
    page_n: int,
    page_total: int,
    header_height_frac: float = 0.055,
):
    """Add a header band across the top of the figure with:

        [Company name BOLD LEFT]   [Project name CENTERED]   [Page n/N + date RIGHT]
        ────────────────────────────────────────────────────────────────────
    """
    c = design.cfg.cartouche
    date = c.date or _dt.date.today().isoformat()
    company = c.company_name.strip() or "—"
    projet = c.projet or "—"

    ax = fig.add_axes((0.0, 1.0 - header_height_frac, 1.0, header_height_frac))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_axis_off()

    # Soft band background
    band = Rectangle((0, 0), 1, 1, facecolor="#F2F2F2",
                     edgecolor="none", zorder=0)
    ax.add_patch(band)
    # Bottom separator
    ax.plot([0.005, 0.995], [0.0, 0.0], color="#B23A48",
            linewidth=1.4, zorder=2)

    # Left — company name
    ax.text(0.012, 0.55, company,
            fontsize=14, fontweight="bold", family="sans-serif",
            color="#1C1C1C", va="center", ha="left", zorder=3)
    # Centre — project name + indice
    centre_text = (f"{projet}     •     Indice {c.indice}"
                   if projet != "—" else f"Indice {c.indice}")
    ax.text(0.5, 0.55, centre_text,
            fontsize=10, family="sans-serif",
            color="#1C1C1C", va="center", ha="center", zorder=3)
    # Right — page X/Y + date
    ax.text(0.988, 0.55, f"{page_title}  •  Page {page_n}/{page_total}  •  {date}",
            fontsize=9, family="sans-serif",
            color="#1C1C1C", va="center", ha="right", zorder=3)


def _drawing_axes(fig: plt.Figure,
                  header_frac: float = 0.055,
                  footer_frac: float = 0.025,
                  side_frac: float = 0.020):
    """Create the main drawing axes below the header. Returns the Axes."""
    return fig.add_axes((
        side_frac, footer_frac,
        1.0 - 2 * side_frac,
        1.0 - header_frac - footer_frac,
    ))


# ─────────────────────────────────────────────────────────────────────────────
# Cover page
# ─────────────────────────────────────────────────────────────────────────────

def _box(ax, x0, y0, w, h, *, fc="white", ec="#1C1C1C", lw=1.0, zorder=1):
    """Helper: draw a filled rectangle with border, in axes coords."""
    ax.add_patch(Rectangle((x0, y0), w, h,
                           facecolor=fc, edgecolor=ec,
                           linewidth=lw, zorder=zorder))


def _box_header(ax, x0, y0, w, h, title,
                title_color="#FFFFFF", bg="#B23A48", font=10):
    """A sub-section header band — coloured strip with bold white title."""
    ax.add_patch(Rectangle((x0, y0), w, h,
                           facecolor=bg, edgecolor="none", zorder=2))
    ax.text(x0 + 0.012, y0 + h / 2, title,
            fontsize=font, fontweight="bold",
            ha="left", va="center", color=title_color,
            family="sans-serif", zorder=3)


def _cover_page(pdf: PdfPages, design: "RoadDesign", title: str,
                page_size_in: Tuple[float, float], n_pages: int):
    """Professional BET-cartouche-style cover page.

    Layout (axes coords; bottom-left = 0,0):

      ╔══════════════════════════════════════════════════════════╗
      ║   Top band — company name in 38 pt + red accent          ║
      ║   Document-type pill ("DOSSIER DE PROJET")               ║
      ║                                                          ║
      ║   ┌──────── PROJECT TITLE  (28-32 pt) ─────────┐         ║
      ║   │                                            │         ║
      ║   └────────────────────────────────────────────┘         ║
      ║                                                          ║
      ║   ┌── INFORMATIONS PROJET ────────────────────┐          ║
      ║   │ key │ value  (10 rows in a clean grid)    │          ║
      ║   └───────────────────────────────────────────┘          ║
      ║                                                          ║
      ║   ┌── CUBATURES ──────────────────────────────┐          ║
      ║   │ Déblai / Remblai / Bilan  with bar chart  │          ║
      ║   └───────────────────────────────────────────┘          ║
      ║                                                          ║
      ║   ┌── INDICE/DATE/N°PLAN/PAGES  4-cell strip ─┐          ║
      ║   └───────────────────────────────────────────┘          ║
      ║                                                          ║
      ║   Footer red line + generation note                      ║
      ╚══════════════════════════════════════════════════════════╝
    """
    c = design.cfg.cartouche
    cfg = design.cfg
    pk_min = float(design.vert_pks.min())
    pk_max = float(design.vert_pks.max())
    L = pk_max - pk_min
    cub = design.cubatures
    # "is_portrait" → use compact typography (A4 or A3). Otherwise (A1
    # landscape) use larger typography.
    is_portrait = page_size_in[1] > page_size_in[0]
    is_a4 = is_portrait  # legacy alias used by the typography branch below

    fig = plt.figure(figsize=page_size_in)
    fig.patch.set_facecolor("white")
    ax = fig.add_axes((0, 0, 1, 1))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.set_axis_off()

    # Page-format-aware sizing (A1 cover gets bigger fonts than A4)
    if is_a4:
        FS_COMPANY  = 30
        FS_PROJECT  = 22
        FS_HEAD     = 10
        FS_ROW      = 10
        FS_CUB_VAL  = 13
        FS_PILL     = 9
        H_BANNER    = 0.085
        BOX_LEFT    = 0.08
        BOX_RIGHT   = 0.92
    else:  # A1 landscape
        FS_COMPANY  = 44
        FS_PROJECT  = 36
        FS_HEAD     = 14
        FS_ROW      = 13
        FS_CUB_VAL  = 18
        FS_PILL     = 12
        H_BANNER    = 0.085
        BOX_LEFT    = 0.13
        BOX_RIGHT   = 0.87

    # ── Top band: company name + red accent line ─────────────────────
    ax.text(0.5, 0.945, c.company_name.strip(),
            fontsize=FS_COMPANY, fontweight="bold", ha="center", va="center",
            family="sans-serif", color="#1C1C1C")
    ax.plot([BOX_LEFT, BOX_RIGHT], [0.905, 0.905],
            color="#B23A48", linewidth=2.4, solid_capstyle="round")
    ax.text(0.5, 0.880, "ROAD DESIGNER V 1.0",
            fontsize=FS_HEAD - 1, ha="center", va="center",
            fontstyle="italic", color="#5A5A5A", family="sans-serif")

    # Document-type pill
    pill_w = 0.34 if is_a4 else 0.26
    pill_h = 0.028
    pill_x = 0.5 - pill_w / 2
    pill_y = 0.842
    ax.add_patch(FancyBboxPatch(
        (pill_x, pill_y), pill_w, pill_h,
        boxstyle="round,pad=0.005,rounding_size=0.012",
        facecolor="#1C1C1C", edgecolor="none", zorder=2,
    ))
    ax.text(0.5, pill_y + pill_h / 2, "D O S S I E R   D E   P R O J E T",
            fontsize=FS_PILL, fontweight="bold",
            ha="center", va="center", color="white",
            family="sans-serif", zorder=3)

    # ── Project title box ────────────────────────────────────────────
    title_y = 0.74
    title_h = 0.075
    _box(ax, BOX_LEFT, title_y, BOX_RIGHT - BOX_LEFT, title_h,
         fc="#F7F2F3", ec="#B23A48", lw=1.5)
    ax.text(0.5, title_y + title_h / 2 + 0.012,
            c.projet.strip() or "— Projet à renseigner —",
            fontsize=FS_PROJECT, fontweight="bold", ha="center", va="center",
            family="sans-serif", color="#1C1C1C")
    ax.text(0.5, title_y + title_h / 2 - 0.020, title,
            fontsize=FS_HEAD, ha="center", va="center",
            family="sans-serif", color="#5A5A5A", fontstyle="italic")

    # ── Project info box ─────────────────────────────────────────────
    info_y = 0.45
    info_h = 0.27
    _box(ax, BOX_LEFT, info_y, BOX_RIGHT - BOX_LEFT, info_h,
         fc="white", ec="#1C1C1C", lw=0.8)
    _box_header(ax, BOX_LEFT, info_y + info_h - 0.030,
                BOX_RIGHT - BOX_LEFT, 0.030,
                "INFORMATIONS PROJET", font=FS_HEAD)

    info_rows = [
        ("Maître d'ouvrage",   c.maitre_ouvrage or "—"),
        ("Bureau d'études",    c.bet or "—"),
        ("Concepteur",         c.designer or "—"),
        ("Catégorie REFT",     f"{cfg.road_category}  ({cfg.design_speed:.0f} km/h)"),
        ("Longueur du tracé",  f"{L:.1f} m   (PK {pk_min:.1f} → {pk_max:.1f})"),
        ("Échelle plan PDF",   _scale_label(cfg.pdf_plan_h_scale,
                                            cfg.pdf_plan_v_scale,
                                            default="auto-ajusté")),
        ("Échelle PT PDF",     _scale_label(cfg.pdf_pt_h_scale,
                                            cfg.pdf_pt_v_scale,
                                            default="auto (1:1)")),
    ]
    row_top = info_y + info_h - 0.045
    row_step = (info_h - 0.050) / max(len(info_rows), 1)
    for k, (lbl, val) in enumerate(info_rows):
        y = row_top - k * row_step
        ax.text(BOX_LEFT + 0.014, y, lbl,
                fontsize=FS_ROW, family="sans-serif",
                color="#5A5A5A", va="center")
        ax.text(BOX_LEFT + (BOX_RIGHT - BOX_LEFT) * 0.42, y, val,
                fontsize=FS_ROW, family="monospace",
                color="#1C1C1C", va="center", fontweight="bold")
        # subtle divider
        if k < len(info_rows) - 1:
            ax.plot([BOX_LEFT + 0.014, BOX_RIGHT - 0.014],
                    [y - row_step / 2, y - row_step / 2],
                    color="#E0E0E0", linewidth=0.4)

    # ── Cubature box w/ horizontal bar chart ─────────────────────────
    cub_y = 0.23
    cub_h = 0.19
    if cub is not None:
        _box(ax, BOX_LEFT, cub_y, BOX_RIGHT - BOX_LEFT, cub_h,
             fc="white", ec="#1C1C1C", lw=0.8)
        _box_header(ax, BOX_LEFT, cub_y + cub_h - 0.030,
                    BOX_RIGHT - BOX_LEFT, 0.030,
                    "CUBATURES (méthode des aires moyennes)",
                    font=FS_HEAD)

        bar_max = max(cub.total_deb, cub.total_rem, 1.0)
        bar_x = BOX_LEFT + 0.20
        bar_w_max = (BOX_RIGHT - BOX_LEFT) * 0.55
        bar_h = 0.022

        def _draw_bar(y, label, value, color):
            ax.text(BOX_LEFT + 0.014, y, label, fontsize=FS_ROW,
                    family="sans-serif", color="#5A5A5A", va="center")
            ax.text(BOX_LEFT + 0.14, y, f"{value:>10,.1f} m³"
                    .replace(",", " "),
                    fontsize=FS_CUB_VAL, family="monospace",
                    color="#1C1C1C", va="center", fontweight="bold")
            ax.add_patch(Rectangle(
                (bar_x, y - bar_h / 2),
                bar_w_max * (abs(value) / bar_max), bar_h,
                facecolor=color, edgecolor="none", alpha=0.85,
            ))

        _draw_bar(cub_y + cub_h - 0.065, "Déblai",  cub.total_deb,  "#B23A48")
        _draw_bar(cub_y + cub_h - 0.105, "Remblai", cub.total_rem,  "#3A7D44")

        # Bilan callout
        sign = "Excédent → évacuer" if cub.balance < 0 else "Déficit → emprunter"
        sign_color = "#B23A48" if cub.balance < 0 else "#D97706"
        ax.text(BOX_LEFT + 0.014, cub_y + cub_h - 0.150, "Bilan",
                fontsize=FS_ROW, family="sans-serif", color="#5A5A5A", va="center")
        ax.text(BOX_LEFT + 0.14, cub_y + cub_h - 0.150,
                f"{cub.balance:>+10,.1f} m³".replace(",", " "),
                fontsize=FS_CUB_VAL, family="monospace",
                color="#1C1C1C", va="center", fontweight="bold")
        ax.text(BOX_LEFT + 0.45, cub_y + cub_h - 0.150,
                f"({sign})", fontsize=FS_ROW, color=sign_color,
                family="sans-serif", va="center", fontstyle="italic")

    # ── 4-cell footer strip: N° plan / Indice / Date / Pages ────────
    strip_y = 0.10
    strip_h = 0.10
    strip_w = BOX_RIGHT - BOX_LEFT
    cell_w = strip_w / 4
    cells = [
        ("N° de plan", c.plan_n or "PLAN"),
        ("Indice",     c.indice),
        ("Date",       c.date or _dt.date.today().isoformat()),
        ("Nombre de pages", f"{n_pages} + couverture"),
    ]
    for i, (lbl, val) in enumerate(cells):
        x0 = BOX_LEFT + i * cell_w
        _box(ax, x0, strip_y, cell_w, strip_h,
             fc="white", ec="#1C1C1C", lw=0.8)
        # red accent on top
        ax.add_patch(Rectangle((x0, strip_y + strip_h - 0.006),
                               cell_w, 0.006,
                               facecolor="#B23A48", edgecolor="none"))
        ax.text(x0 + cell_w / 2, strip_y + strip_h - 0.024, lbl,
                fontsize=FS_HEAD - 2, color="#5A5A5A",
                family="sans-serif", ha="center", va="center")
        ax.text(x0 + cell_w / 2, strip_y + strip_h * 0.40, val,
                fontsize=FS_PROJECT - 6, fontweight="bold",
                family="sans-serif", color="#1C1C1C",
                ha="center", va="center")

    # ── REFT warnings (small, only if any) ──────────────────────────
    if design.tangent_warnings:
        ax.text(BOX_LEFT, 0.075,
                f"⚠ {len(design.tangent_warnings)} avertissement(s) REFT — "
                "voir l'onglet 2 du fichier Excel.",
                fontsize=FS_ROW - 1, color="#D97706",
                family="sans-serif", ha="left", va="center")

    # ── Footer ──────────────────────────────────────────────────────
    ax.plot([BOX_LEFT, BOX_RIGHT], [0.045, 0.045],
            color="#B23A48", linewidth=1.0)
    ax.text(0.5, 0.025,
            "Document généré automatiquement par Road Designer V 1.0 — "
            "DXF + XLSX + PDF joints",
            fontsize=FS_ROW - 2, fontstyle="italic", ha="center", va="center",
            family="sans-serif", color="#5A5A5A")

    pdf.savefig(fig); plt.close(fig)


def _scale_label(h: Optional[int], v: Optional[int], default: str = "auto") -> str:
    """Render a "H 1:N V 1:M" label, or a default phrase when unset."""
    if h is None and v is None:
        return default
    h_part = f"H 1:{h}" if h else "H auto"
    v_part = f"V 1:{v}" if v else "V auto"
    return f"{h_part}   {v_part}"


# ═════════════════════════════════════════════════════════════════════════════
# (a) PLAN + PROFIL EN LONG — A1 landscape, one page per sheet_length_pk
# ═════════════════════════════════════════════════════════════════════════════

def _draw_plan_window(ax: plt.Axes, design: "RoadDesign",
                      pk_start: float, pk_end: float):
    """Draw the plan view clipped to the PK window."""
    cfg = design.cfg

    # Dense polylines clipped to window
    mask = (design.dense_pks >= pk_start - 0.5) & (design.dense_pks <= pk_end + 0.5)
    if not mask.any():
        return
    dense_idx = np.where(mask)[0]
    x_d = design.dense_x_rot[dense_idx]
    y_d = design.dense_y_rot[dense_idx]
    ax.plot(x_d, y_d, color="#1E3A8A", linewidth=1.0, zorder=4, label="Axe")

    # Road edges
    from .geometry_engine import offset_points
    axis = np.column_stack((x_d, y_d))
    if len(axis) >= 2:
        left, right = offset_points(axis, cfg.road_width)
        ax.plot(left[:, 0], left[:, 1], color="#808080", linewidth=0.6, zorder=3)
        ax.plot(right[:, 0], right[:, 1], color="#808080", linewidth=0.6, zorder=3)

    # Stations within window with bubbles
    v_mask = (design.vert_pks >= pk_start - 0.5) & (design.vert_pks <= pk_end + 0.5)
    for i in np.where(v_mask)[0]:
        x, y = design.vert_x_rot[i], design.vert_y_rot[i]
        # cutting line + bubble
        if 0 < i < len(design.vert_pks) - 1:
            dx = design.vert_x_rot[i + 1] - design.vert_x_rot[i - 1]
            dy = design.vert_y_rot[i + 1] - design.vert_y_rot[i - 1]
        elif i == 0:
            dx = design.vert_x_rot[1] - design.vert_x_rot[0]
            dy = design.vert_y_rot[1] - design.vert_y_rot[0]
        else:
            dx = design.vert_x_rot[-1] - design.vert_x_rot[-2]
            dy = design.vert_y_rot[-1] - design.vert_y_rot[-2]
        L = np.hypot(dx, dy)
        if L == 0:
            continue
        nx, ny = -dy / L, dx / L
        half = cfg.cutting_line_length / 2
        ax.plot([x - nx * half, x + nx * half], [y - ny * half, y + ny * half],
                color="#D97706", linewidth=0.7, zorder=4)
        bx = x + nx * cfg.annotation_offset
        by = y + ny * cfg.annotation_offset
        ax.add_patch(plt.Circle((bx, by), 1.8, facecolor="white",
                                edgecolor="#0891B2", linewidth=0.9, zorder=5))
        ax.text(bx, by, f"P{i + 1}", fontsize=6, ha="center", va="center",
                color="#0891B2", zorder=6)

    # Arc annotations within window
    for arc in design.get_arc_annotations():
        if arc["end_pk"] < pk_start or arc["start_pk"] > pk_end:
            continue
        ax.plot(arc["arrow_points_rot"][:, 0],
                arc["arrow_points_rot"][:, 1],
                color="#0891B2", linewidth=0.9, zorder=4)
        ax.text(arc["midpoint_rot"][0], arc["midpoint_rot"][1],
                arc["label"], fontsize=6.5, ha="center", va="center",
                color="#0891B2", zorder=6,
                bbox=dict(facecolor="white", edgecolor="none",
                          alpha=0.7, pad=0.5))

    # Straight annotations within window
    for line in design.get_line_annotations():
        seg = line["offset_line_rot"]
        ax.plot([seg[0, 0], seg[1, 0]], [seg[0, 1], seg[1, 1]],
                color="#0891B2", linewidth=0.6, zorder=3)
        ax.text(line["midpoint_rot"][0], line["midpoint_rot"][1],
                line["label"], fontsize=6, ha="center", va="center",
                color="#0891B2", zorder=5,
                bbox=dict(facecolor="white", edgecolor="none",
                          alpha=0.7, pad=0.3))


def _draw_profile_window(
    ax: plt.Axes, design: "RoadDesign", pk_start: float, pk_end: float,
):
    """Draw the profile en long (TN + projet) + cut/fill labels."""
    cfg = design.cfg
    (prof_x, ground_y, proj_y,
     prof_x_dense, proj_y_dense, base_y) = design.get_profile_data()

    # Dense polylines clipped to window
    dmask = (design.dense_pks >= pk_start - 0.5) & (design.dense_pks <= pk_end + 0.5)
    if dmask.any():
        ax.plot(prof_x_dense[dmask], proj_y_dense[dmask],
                color="#B23A48", linewidth=1.2, zorder=4, label="Projet")

    # TN (uses vertex values — fine since the dense TN is just vertex-sampled here)
    vmask = (design.vert_pks >= pk_start - 0.5) & (design.vert_pks <= pk_end + 0.5)
    ax.plot(prof_x[vmask], ground_y[vmask],
            color="#3A7D44", linewidth=1.2, zorder=4, label="TN")

    # Cut/fill labels
    cub = design.cubatures
    h = cub.h_per_vertex if cub is not None else (
        design.vert_proj_z - design.vert_ground_z
    )
    for i in np.where(vmask)[0]:
        h_val = float(h[i])
        if abs(h_val) < 0.05:
            continue
        label = f"{'Remb' if h_val > 0 else 'Déb'}={abs(h_val):.2f} m"
        color = "#3A7D44" if h_val > 0 else "#B23A48"
        y_proj = base_y + (design.vert_proj_z[i] - design.datum) * cfg.v_scale
        ax.text(prof_x[i] + 0.3, y_proj + 0.7, label,
                fontsize=5, rotation=45, ha="left", va="bottom",
                color=color, zorder=6,
                bbox=dict(facecolor="white", edgecolor="none",
                          alpha=0.6, pad=0.3))

    # Datum label on the left
    ax.text(prof_x[0] - 4, base_y, f"Cote datum = {design.datum:.0f} m",
            fontsize=6, ha="right", va="center", color="#5A5A5A",
            fontstyle="italic")


def _draw_table_window(
    ax: plt.Axes, design: "RoadDesign", pk_start: float, pk_end: float,
    table_top_y: float, table_total_h: float = 75.0,
):
    """Draw the 7-row table (with cubature row) for the PK window."""
    cfg = design.cfg
    cub = design.cubatures
    (nos, lengths, pks, ctn, cproj, col_x, diffs) = design.get_table_data()

    vmask = (design.vert_pks >= pk_start - 0.5) & (design.vert_pks <= pk_end + 0.5)
    idx = np.where(vmask)[0]
    if len(idx) < 1:
        return
    cx = [col_x[i] for i in idx]
    x_min = min(cx) - 4.0
    x_max = max(cx) + 4.0

    row_labels = [
        "N° du Profil",
        "Distance Partielle",
        "Distance Cumulée (PK)",
        "Cote TN",
        "Cote Projet",
        "Pente (%)",
        "Cub. Déb. / Remb. (m³)",
    ]
    row_h = [6.0, 6.0, 12.0, 12.0, 12.0, 10.0, 17.0]
    row_h_total = sum(row_h)
    # Scale rows so the table fits in table_total_h
    scale = table_total_h / row_h_total
    row_h = [h * scale for h in row_h]

    row_y = [table_top_y]
    for h in row_h:
        row_y.append(row_y[-1] - h)

    # Title column to the left
    title_w = 20.0
    x_title = x_min - title_w

    # Frame
    for ry in row_y:
        ax.plot([x_title, x_max], [ry, ry], color="#1C1C1C", linewidth=0.5)
    for cxv in [x_title, x_min, x_max] + list(cx):
        ax.plot([cxv, cxv], [row_y[0], row_y[-1]],
                color="#1C1C1C", linewidth=0.4)
    for i, lab in enumerate(row_labels):
        ax.text(x_title + 0.5, (row_y[i] + row_y[i + 1]) / 2, lab,
                fontsize=5.5, ha="left", va="center", color="#1C1C1C")

    # Cell contents
    for k, i in enumerate(idx):
        x = float(col_x[i])
        # 0 — Profil no
        ax.text(x, (row_y[0] + row_y[1]) / 2, nos[i],
                fontsize=6, fontweight="bold", ha="center", va="center",
                color="#0891B2")
        # 1 — Dist. partielle (mid block between i-1 and i)
        if k > 0:
            prev_i = idx[k - 1]
            mid_x = (col_x[prev_i] + col_x[i]) / 2
            ax.text(mid_x, (row_y[1] + row_y[2]) / 2,
                    f"{float(design.seg_lengths[i]):.2f}",
                    fontsize=5.5, ha="center", va="center", color="#1C1C1C")
        # 2 — PK (rotated 90°)
        ax.text(x, (row_y[2] + row_y[3]) / 2, pks[i],
                fontsize=5.5, ha="center", va="center", rotation=90,
                color="#1C1C1C")
        # 3 — Cote TN
        ax.text(x, (row_y[3] + row_y[4]) / 2, ctn[i],
                fontsize=5.5, ha="center", va="center", rotation=90,
                color="#3A7D44")
        # 4 — Cote Projet
        ax.text(x, (row_y[4] + row_y[5]) / 2, cproj[i],
                fontsize=5.5, ha="center", va="center", rotation=90,
                color="#B23A48")
        # 5 — Pente entrante (%)
        if k > 0:
            prev_i = idx[k - 1]
            dpk = design.vert_pks[i] - design.vert_pks[prev_i]
            if dpk > 0:
                pente = 100.0 * (design.v_align.get_z(design.vert_pks[i])
                                 - design.v_align.get_z(design.vert_pks[prev_i])) / dpk
                mid_x = (col_x[prev_i] + col_x[i]) / 2
                ax.text(mid_x, (row_y[5] + row_y[6]) / 2,
                        f"{pente:+.2f}",
                        fontsize=5.5, ha="center", va="center",
                        color=("#3A7D44" if pente >= 0 else "#B23A48"))
        # 6 — Cubatures
        if cub is not None and k > 0:
            prev_i = idx[k - 1]
            # Find matching segment volume by index in original arrays
            v_deb = float(cub.V_deb_per_seg[i - 1])
            v_rem = float(cub.V_rem_per_seg[i - 1])
            mid_x = (col_x[prev_i] + col_x[i]) / 2
            y_top = row_y[6] - row_h[6] * 0.30
            y_bot = row_y[6] - row_h[6] * 0.70
            if v_deb > 0.5:
                ax.text(mid_x, y_top, f"D {v_deb:.0f}",
                        fontsize=5, ha="center", va="center", color="#B23A48")
            if v_rem > 0.5:
                ax.text(mid_x, y_bot, f"R {v_rem:.0f}",
                        fontsize=5, ha="center", va="center", color="#3A7D44")


def _draw_grade_diagram_band(
    ax: plt.Axes, design: "RoadDesign", pk_start: float, pk_end: float,
    y_top: float, y_bot: float,
):
    """Slope-and-length sketch under the table (row 5 in the DXF)."""
    y_mid = (y_top + y_bot) / 2
    for grade, pa, pb in zip(design.v_align.grades,
                              design.v_align.pvi[:-1],
                              design.v_align.pvi[1:]):
        if pb[0] < pk_start or pa[0] > pk_end:
            continue
        s = design.pk_to_x(max(pa[0], pk_start))
        e = design.pk_to_x(min(pb[0], pk_end))
        if grade > 0:
            y1, y2 = y_bot + 0.5, y_top - 0.5
        else:
            y1, y2 = y_top - 0.5, y_bot + 0.5
        ax.plot([s, e], [y1, y2], color="#B23A48", linewidth=0.6)
        ax.text((s + e) / 2, y_mid + 0.3, f"P={grade * 100:.2f}%",
                fontsize=5, ha="center", va="bottom", color="#B23A48")
        ax.text((s + e) / 2, y_mid - 0.3, f"L={pb[0] - pa[0]:.0f}m",
                fontsize=4.5, ha="center", va="top", color="#5A5A5A")


def _draw_bruckner_band(
    ax: plt.Axes, design: "RoadDesign", pk_start: float, pk_end: float,
    y_top: float, y_bot: float,
):
    """Bruckner curve band — same PK X, fits between (y_top, y_bot)."""
    if design.cubatures is None:
        return
    cub = design.cubatures
    y_zero = (y_top + y_bot) / 2

    # Frame + baseline
    ax.plot([design.pk_to_x(pk_start), design.pk_to_x(pk_end)],
            [y_zero, y_zero], color="#1C1C1C", linewidth=0.4, linestyle="--")
    ax.text(design.pk_to_x(pk_start) - 4, y_zero,
            "Bruckner", fontsize=5.5, ha="right", va="center",
            color="#7C2D92", fontstyle="italic")

    # Map M(PK) to y inside the band
    band_half = (y_top - y_bot) / 2 * 0.85
    M_max = max(abs(cub.bruckner.min()), abs(cub.bruckner.max()), 1.0)
    scale = band_half / M_max

    vmask = (design.vert_pks >= pk_start - 0.5) & (design.vert_pks <= pk_end + 0.5)
    xs = [design.pk_to_x(pk) for pk in design.vert_pks[vmask]]
    ys = [y_zero + m * scale for m in cub.bruckner[vmask]]
    ax.plot(xs, ys, color="#7C2D92", linewidth=1.0)
    ax.fill_between(xs, ys, y_zero,
                    where=[y >= y_zero for y in ys],
                    color="#7C2D92", alpha=0.18)
    ax.fill_between(xs, ys, y_zero,
                    where=[y < y_zero for y in ys],
                    color="#D97706", alpha=0.18)

    # M end label
    ax.text(design.pk_to_x(pk_end) + 1, y_zero,
            f"M(fin)={cub.balance:+.0f} m³",
            fontsize=6, ha="left", va="center", color="#7C2D92")


def _plan_h_geometry(cfg, pk_start: float, pk_end: float
                     ) -> Tuple[float, float]:
    """Compute (left_frac, width_frac) for the plan/profile axes on A1.

    If ``cfg.pdf_plan_h_scale`` is set, the axes width is sized so that
    1 m on the road = ``1000 / pdf_plan_h_scale`` mm on paper exactly.
    Otherwise we use the historical auto-fit (4 % margin each side).
    """
    A1_W_MM_LOCAL = 841.0
    pk_len = pk_end - pk_start
    if cfg.pdf_plan_h_scale:
        target_w_mm = pk_len * 1000.0 / float(cfg.pdf_plan_h_scale)
        # Allow up to 95 % of page width
        max_w_mm = A1_W_MM_LOCAL * 0.95
        actual_w_mm = min(target_w_mm, max_w_mm)
        left_frac = (A1_W_MM_LOCAL - actual_w_mm) / (2 * A1_W_MM_LOCAL)
        width_frac = actual_w_mm / A1_W_MM_LOCAL
    else:
        left_frac, width_frac = 0.04, 0.92
    return left_frac, width_frac


def _render_plan_page(
    pdf: PdfPages, design: "RoadDesign",
    pk_start: float, pk_end: float, page_n: int, page_total: int,
):
    """Render a single plan-+-profile-+-table-+-Bruckner page."""
    fig = plt.figure(figsize=A1_LANDSCAPE_IN, facecolor="white")
    _draw_company_header(fig, design,
                         f"Plan + Profil — PK {pk_start:.0f} → {pk_end:.0f}",
                         page_n, page_total)

    left_frac, width_frac = _plan_h_geometry(design.cfg, pk_start, pk_end)

    # Three stacked drawing areas in the body — vertically split: top half
    # for plan, bottom half for profile + table + Bruckner. If a user H
    # scale is forced and produces narrow axes, we still keep the same
    # vertical split so the layout stays balanced.
    ax_plan = fig.add_axes((left_frac, 0.50, width_frac, 0.40))
    ax_main = fig.add_axes((left_frac, 0.04, width_frac, 0.44))
    for ax in (ax_plan, ax_main):
        ax.set_aspect("equal")
        ax.set_axis_off()

    # ── Plan
    _draw_plan_window(ax_plan, design, pk_start, pk_end)
    x0_plan = design.pk_to_x(pk_start) - 30
    x1_plan = design.pk_to_x(pk_end) + 30
    y_plan_lo, y_plan_hi = design.vert_y_rot.min() - 25, design.vert_y_rot.max() + 25
    ax_plan.set_xlim(x0_plan, x1_plan)
    ax_plan.set_ylim(y_plan_lo, y_plan_hi)
    ax_plan.set_title(f"Tracé en plan — PK {pk_start:.0f} → {pk_end:.0f}",
                      fontsize=11, color="#1C1C1C", pad=4)

    # ── Profile + table + grade band + Bruckner in ax_main
    (prof_x, ground_y, proj_y,
     prof_x_dense, proj_y_dense, base_y) = design.get_profile_data()
    _draw_profile_window(ax_main, design, pk_start, pk_end)

    # Compute Y stack
    table_top = base_y - 8.0
    table_h = 60.0
    table_bot = table_top - table_h
    grade_top = table_bot - 2.0
    grade_bot = grade_top - 8.0
    bruck_top = grade_bot - 4.0
    bruck_bot = bruck_top - 20.0

    _draw_table_window(ax_main, design, pk_start, pk_end, table_top, table_h)
    _draw_grade_diagram_band(ax_main, design, pk_start, pk_end,
                              grade_top, grade_bot)
    _draw_bruckner_band(ax_main, design, pk_start, pk_end,
                         bruck_top, bruck_bot)

    # Vertical guides — profile vertices down to table top (perfectly vertical)
    vmask = (design.vert_pks >= pk_start - 0.5) & (design.vert_pks <= pk_end + 0.5)
    for i in np.where(vmask)[0]:
        ax_main.plot([prof_x[i], prof_x[i]],
                     [ground_y[i], table_top],
                     color="#D97706", linewidth=0.35, linestyle=":")

    x0_main = design.pk_to_x(pk_start) - 30
    x1_main = design.pk_to_x(pk_end) + 30
    ax_main.set_xlim(x0_main, x1_main)
    ax_main.set_ylim(bruck_bot - 4.0, base_y
                     + (design.dense_ground_z.max() - design.datum)
                     * design.cfg.v_scale + 6.0)
    ax_main.set_title("Profil en long + Tableau + Diagramme de Bruckner",
                      fontsize=11, color="#1C1C1C", pad=4)

    pdf.savefig(fig); plt.close(fig)


# ─────────────────────────────────────────────────────────────────────────────
# Public — plan PDF
# ─────────────────────────────────────────────────────────────────────────────

def _plan_windows(design: "RoadDesign") -> List[Tuple[float, float]]:
    cfg = design.cfg
    pk_min = float(design.vert_pks.min())
    pk_max = float(design.vert_pks.max())
    n = max(1, int(np.ceil((pk_max - pk_min) / cfg.sheet_length_pk)))
    out = []
    for k in range(n):
        a = pk_min + k * cfg.sheet_length_pk
        b = min(pk_max, a + cfg.sheet_length_pk)
        out.append((a, b))
    return out


def write_plan_pdf(dxf_path: Union[str, Path, None],
                   out_path: Union[str, Path],
                   design: "RoadDesign") -> Path:
    """One PDF page per ``sheet_length_pk`` window of road."""
    out_path = Path(out_path)
    windows = _plan_windows(design)
    n_pages = len(windows)
    with PdfPages(out_path) as pdf:
        _cover_page(pdf, design, "Plan + Profil en long — par sections",
                    A1_LANDSCAPE_IN, n_pages)
        for k, (a, b) in enumerate(windows, start=1):
            _render_plan_page(pdf, design, a, b, k, n_pages)
    print(f"PDF generated: {out_path}  ({n_pages} pages + cover)")
    return out_path


def to_plan_pdf_bytes(dxf_path, design: "RoadDesign") -> bytes:
    buf = io.BytesIO()
    windows = _plan_windows(design)
    n = len(windows)
    with PdfPages(buf) as pdf:
        _cover_page(pdf, design, "Plan + Profil en long — par sections",
                    A1_LANDSCAPE_IN, n)
        for k, (a, b) in enumerate(windows, start=1):
            _render_plan_page(pdf, design, a, b, k, n)
    return buf.getvalue()


# ═════════════════════════════════════════════════════════════════════════════
# (b) PROFILS EN TRAVERS — A4 portrait, properly sized cross-sections
# ═════════════════════════════════════════════════════════════════════════════

# PT drawing area (mm) — A3 portrait is 297 × 420 mm.  We use 285 mm wide
# (96 %) and up to 335 mm tall, leaving room for the company header, the
# project info block, and the cubature footer.
_PT_DRAW_W_MM = 285.0
_PT_DRAW_H_MM = 335.0

# Default vertical exaggeration when neither H nor V is provided. 1.0 means
# **no exaggeration** (V = H — geometrically honest cross-section, the BET
# standard for "profil en travers à l'échelle vraie").
_DEFAULT_VERT_EXAG = 1.0

_SCALE_CANDIDATES = [
    20, 25, 50, 100, 125, 150, 200, 250, 300, 400,
    500, 750, 1000, 1500, 2000,
]


def _pick_pt_scales(
    t_range: float,
    z_range: float,
    user_scale_h: Optional[int] = None,
    user_scale_v: Optional[int] = None,
) -> Tuple[int, int, float, float]:
    """Pick H and V scales for the cross-section page.

    Resolution rules
    ----------------
    * If ``user_scale_h`` is provided, it is used verbatim.
      Otherwise the smallest candidate that fits ``_PT_DRAW_W_MM`` is picked.
    * If ``user_scale_v`` is provided, it is used verbatim.
      Otherwise ``scale_v = scale_h`` (1:1 ratio — no vertical exaggeration).

    Returns ``(scale_h, scale_v, width_mm, height_mm)``.
    """
    def fit(span_m: float, max_mm: float) -> int:
        """Smallest candidate scale whose drawing extent ≤ max_mm."""
        for s in _SCALE_CANDIDATES:
            if span_m * 1000.0 / s <= max_mm:
                return s
        return _SCALE_CANDIDATES[-1]

    scale_h = int(user_scale_h) if user_scale_h else fit(t_range, _PT_DRAW_W_MM)
    if user_scale_v:
        scale_v = int(user_scale_v)
    else:
        # Default to 1:1 ratio — no vertical exaggeration
        scale_v = int(round(scale_h * _DEFAULT_VERT_EXAG))

    width_mm = t_range * 1000.0 / scale_h
    height_mm = z_range * 1000.0 / scale_v
    return scale_h, scale_v, width_mm, height_mm


def _render_pt_page(pdf: PdfPages, design: "RoadDesign", sec,
                    page_n: int, page_total: int):
    """Render one cross-section page (A4 portrait).

    The drawing area is centred horizontally AND vertically inside the body
    of the page (between the header band at the top and the stats footer
    at the bottom). H and V scales are picked independently to fill that
    body without distorting the typical-section break points.
    """
    fig = plt.figure(figsize=PT_PAGE_IN, facecolor="white")
    _draw_company_header(fig, design,
                         f"Profil en travers — PK {sec.pk:.2f}",
                         page_n, page_total)

    ts = np.array([p[0] for p in sec.tn_polyline + sec.proj_polyline])
    zs = np.array([p[1] for p in sec.tn_polyline + sec.proj_polyline])
    t_min, t_max = float(ts.min()), float(ts.max())
    z_min, z_max = float(zs.min()), float(zs.max())
    t_range = max(0.5, t_max - t_min)
    z_range = max(0.5, z_max - z_min)
    scale_h, scale_v, w_mm, h_mm = _pick_pt_scales(
        t_range, z_range,
        user_scale_h=design.cfg.pdf_pt_h_scale,
        user_scale_v=design.cfg.pdf_pt_v_scale,
    )

    page_w_mm = PT_PAGE_W_MM
    page_h_mm = PT_PAGE_H_MM

    # Body extent: under the title/stats block (top ≈ 84 %) down to just
    # above the stats footer (bottom ≈ 9 %).
    body_top_frac = 0.84
    body_bot_frac = 0.09
    body_w_mm = page_w_mm
    body_h_mm = (body_top_frac - body_bot_frac) * page_h_mm

    # Horizontally centre, vertically ANCHOR near the top of the body —
    # cross-sections are short in Z, so centring leaves a big gap above
    # that reads as awkward whitespace. Top-anchoring keeps the drawing
    # close to the title block and pushes any leftover space below, where
    # the eye expects nothing (above the footer).
    left = ((body_w_mm - w_mm) / 2) / page_w_mm
    width_frac = w_mm / page_w_mm
    height_frac = h_mm / page_h_mm
    bottom = body_top_frac - height_frac - 0.02     # 2 % gap below stats
    ax = fig.add_axes((left, bottom, width_frac, height_frac))
    ax.set_aspect(scale_h / scale_v)  # H/V exaggeration via aspect ratio
    ax.set_xlim(t_min - 0.5, t_max + 0.5)
    ax.set_ylim(z_min - 0.3, z_max + 0.3)

    # Hatched cut / fill polygons
    for poly in sec.fill_polygons:
        if len(poly) >= 3:
            ax.add_patch(MplPolygon(
                poly, closed=True, facecolor="#3A7D44", alpha=0.18,
                edgecolor="#3A7D44", linewidth=0.4, hatch="\\\\\\\\",
            ))
    for poly in sec.cut_polygons:
        if len(poly) >= 3:
            ax.add_patch(MplPolygon(
                poly, closed=True, facecolor="#B23A48", alpha=0.18,
                edgecolor="#B23A48", linewidth=0.4, hatch="////",
            ))

    # TN
    tn_t = [p[0] for p in sec.tn_polyline]
    tn_z = [p[1] for p in sec.tn_polyline]
    ax.plot(tn_t, tn_z, color="#3A7D44", linewidth=1.4, label="TN")

    # Projet
    pj_t = [p[0] for p in sec.proj_polyline]
    pj_z = [p[1] for p in sec.proj_polyline]
    ax.plot(pj_t, pj_z, color="#B23A48", linewidth=1.4, label="Projet")

    # Axe tick
    ax.axvline(0.0, color="#0891B2", linewidth=0.6, linestyle=":")
    ax.text(0.0, z_max + 0.05, "Axe", color="#0891B2", fontsize=7,
            ha="center", va="bottom")

    # Break-point labels
    for t, z, label in sec.projet_break_points:
        if label == "axe":
            continue
        ax.plot(t, z, marker="o", markersize=2.2,
                markeredgecolor="#B23A48", markerfacecolor="white",
                markeredgewidth=0.7)
        ax.annotate(
            label, xy=(t, z), xytext=(0, -7),
            textcoords="offset points",
            fontsize=6, ha="center", va="top", color="#5A5A5A",
        )

    # Title and stats — placed BETWEEN the header band (top ~5.5 %) and the
    # drawing area (top of body at 0.84). Avoids any overlap with the header.
    fig.text(0.5, 0.905,
             f"Profil en travers — PK {sec.pk:.2f} m",
             fontsize=14, fontweight="bold", ha="center", color="#1C1C1C")
    fig.text(0.5, 0.870,
             f"Cote projet (axe) = {sec.z_axis_proj:.3f} m   •   "
             f"Cote TN (axe) = {sec.z_axis_tn:.3f} m   •   "
             f"h = {sec.z_axis_proj - sec.z_axis_tn:+.3f} m",
             fontsize=9, ha="center", color="#5A5A5A")

    # Footer with areas + scales
    fig.text(0.5, 0.06,
             f"Aire déblai = {sec.cut_area:>7.2f} m²    •    "
             f"Aire remblai = {sec.fill_area:>7.2f} m²",
             fontsize=10, ha="center", color="#1C1C1C")
    fig.text(0.5, 0.04,
             f"Échelles  —  H 1:{scale_h}   V 1:{scale_v}   "
             f"(exagération verticale ×{scale_h / scale_v:.1f})",
             fontsize=8.5, ha="center", color="#5A5A5A", fontstyle="italic")

    # Grid + axis labels
    ax.grid(True, color="#CCCCCC", linewidth=0.3, linestyle="--", alpha=0.7)
    ax.tick_params(axis="both", labelsize=6, color="#5A5A5A")
    ax.set_xlabel("t — perpendiculaire à l'axe (m)", fontsize=7,
                  color="#5A5A5A")
    ax.set_ylabel("Cote (m)", fontsize=7, color="#5A5A5A")
    for spine in ax.spines.values():
        spine.set_color("#9A9A9A")
        spine.set_linewidth(0.5)
    ax.legend(loc="upper right", fontsize=7, framealpha=0.85)

    pdf.savefig(fig); plt.close(fig)


def write_pt_pdf(dxf_path: Union[str, Path, None],
                 out_path: Union[str, Path],
                 design: "RoadDesign") -> Path:
    """One PDF page per cross-section."""
    out_path = Path(out_path)
    sections = getattr(design, "sections", None)
    if not sections:
        # Fall back — compute on demand
        from .cross_section import all_sections
        sections = all_sections(design)
    n = len(sections)
    with PdfPages(out_path) as pdf:
        _cover_page(pdf, design, "Profils en travers",
                    PT_PAGE_IN, n)
        for k, sec in enumerate(sections, start=1):
            _render_pt_page(pdf, design, sec, k, n)
    print(f"PDF generated: {out_path}  ({n} pages + cover)")
    return out_path


def to_pt_pdf_bytes(dxf_path, design: "RoadDesign") -> bytes:
    sections = getattr(design, "sections", None)
    if not sections:
        from .cross_section import all_sections
        sections = all_sections(design)
    n = len(sections)
    buf = io.BytesIO()
    with PdfPages(buf) as pdf:
        _cover_page(pdf, design, "Profils en travers",
                    PT_PAGE_IN, n)
        for k, sec in enumerate(sections, start=1):
            _render_pt_page(pdf, design, sec, k, n)
    return buf.getvalue()
