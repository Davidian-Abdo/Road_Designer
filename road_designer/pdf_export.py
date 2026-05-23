"""PDF export — two files driven by the paperspace layouts in the DXF.

(a) ``plan_par_sections.pdf`` — one page per ``PLAN_xx`` layout (Step 8).
    Each page corresponds to ``cfg.sheet_length_pk`` metres of road.

(b) ``profils_en_travers.pdf`` — one page per ``PT_xx`` layout (Step 7).
    Each page is a single cross-section.

We **never** re-implement geometry here — the DXF is the source of truth.
A matplotlib backend driven by ``ezdxf.addons.drawing`` rasterises each
layout to a PDF page. A cover page is prepended in front of each PDF so the
printed deliverable is self-describing.

In-memory variants ``to_plan_pdf_bytes`` and ``to_pt_pdf_bytes`` are required
by the Streamlit UI (rule 9.1 in CLAUDE.md).
"""
from __future__ import annotations

import io
from pathlib import Path
from typing import TYPE_CHECKING, List, Union

import matplotlib
matplotlib.use("Agg")  # Streamlit-Cloud-safe (rule 9.3)

import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

import ezdxf
from ezdxf.addons.drawing import Frontend, RenderContext
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
from ezdxf.addons.drawing.config import Configuration

if TYPE_CHECKING:
    from .road_design import RoadDesign


# ─────────────────────────────────────────────────────────────────────────────
# Paper sizes (mm → inches for matplotlib)
# ─────────────────────────────────────────────────────────────────────────────

MM_PER_INCH = 25.4

A1_LANDSCAPE_IN = (841.0 / MM_PER_INCH, 594.0 / MM_PER_INCH)
A4_PORTRAIT_IN  = (210.0 / MM_PER_INCH, 297.0 / MM_PER_INCH)


# ─────────────────────────────────────────────────────────────────────────────
# Render one DXF layout to a Matplotlib figure
# ─────────────────────────────────────────────────────────────────────────────

def _render_layout_to_figure(doc, layout_name: str, page_size_in):
    """Return a matplotlib Figure of the given paperspace layout."""
    layout = doc.layouts.get(layout_name)
    if layout is None:
        raise KeyError(f"Layout '{layout_name}' not found in DXF.")

    fig, ax = plt.subplots(figsize=page_size_in)
    ax.set_axis_off()
    ax.set_aspect("equal")

    ctx = RenderContext(doc)
    out = MatplotlibBackend(ax)
    Frontend(ctx, out, config=Configuration()).draw_layout(
        layout, finalize=True,
    )
    fig.tight_layout(pad=0.4)
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# Cover page
# ─────────────────────────────────────────────────────────────────────────────

def _cover_page(pdf: PdfPages, design: "RoadDesign", title: str,
                page_size_in, layouts: List[str]):
    """Prepend a one-page cover with project metadata + totals."""
    cfg = design.cfg
    c = cfg.cartouche

    fig = plt.figure(figsize=page_size_in)
    fig.patch.set_facecolor("white")
    ax = fig.add_axes((0, 0, 1, 1))
    ax.set_axis_off()

    pk_min = float(design.vert_pks.min())
    pk_max = float(design.vert_pks.max())
    L = pk_max - pk_min
    cub = design.cubatures

    cubature_lines = []
    if cub is not None:
        cubature_lines = [
            "",
            "Cubatures (méthode des aires moyennes) :",
            f"    Σ Déblai  = {cub.total_deb:>10.1f} m³",
            f"    Σ Remblai = {cub.total_rem:>10.1f} m³",
            f"    Bilan     = {cub.balance:>+10.1f} m³",
        ]

    lines = [
        ("Road Designer V 1.0", 28, "bold"),
        (title,                  18, "regular"),
        ("",                      8, "regular"),
        (f"Projet            : {c.projet or '—'}",                  12, "regular"),
        (f"Maître d'ouvrage  : {c.maitre_ouvrage or '—'}",          12, "regular"),
        (f"Bureau d'études   : {c.bet or '—'}",                     12, "regular"),
        (f"Concepteur        : {c.designer or '—'}",                12, "regular"),
        (f"Indice            : {c.indice}     Date : {c.date or '—'}", 12, "regular"),
        ("",                      8, "regular"),
        (f"Catégorie REFT    : {cfg.road_category}  ({cfg.design_speed:.0f} km/h)",
                                                                    12, "regular"),
        (f"Longueur du tracé : {L:.1f} m   "
         f"(PK {pk_min:.1f} → {pk_max:.1f})",                       12, "regular"),
        (f"Échelles           : H {c.echelle_h}   V {c.echelle_v}", 12, "regular"),
        ("",                      8, "regular"),
        (f"Nombre de pages    : {len(layouts)}",                    12, "regular"),
    ]
    for line in cubature_lines:
        lines.append((line, 12, "regular"))

    if design.tangent_warnings:
        lines.append(("", 8, "regular"))
        lines.append(("Avertissements REFT :", 12, "bold"))
        for w in design.tangent_warnings[:5]:
            lines.append((f"  • {w}", 10, "regular"))
        if len(design.tangent_warnings) > 5:
            lines.append(
                (f"  … et {len(design.tangent_warnings) - 5} autre(s).",
                 10, "regular")
            )

    y = 0.92
    for text, size, weight in lines:
        ax.text(
            0.08, y, text,
            fontsize=size, weight=weight, family="monospace",
            transform=ax.transAxes, va="top",
        )
        y -= (size / 700.0) + 0.018

    pdf.savefig(fig)
    plt.close(fig)


# ─────────────────────────────────────────────────────────────────────────────
# (a) Plan par sections — one page per PLAN_xx layout
# ─────────────────────────────────────────────────────────────────────────────

def _plan_layouts(doc) -> List[str]:
    return sorted(
        name for name in doc.layouts.names_in_taborder()
        if name.startswith("PLAN_")
    )


def _pt_layouts(doc) -> List[str]:
    return sorted(
        name for name in doc.layouts.names_in_taborder()
        if name.startswith("PT_")
    )


def write_plan_pdf(dxf_path: Union[str, Path], out_path: Union[str, Path],
                   design: "RoadDesign") -> Path:
    """Render PLAN_01..PLAN_N to a multi-page A1-landscape PDF."""
    out_path = Path(out_path)
    doc = ezdxf.readfile(dxf_path)
    layouts = _plan_layouts(doc)

    with PdfPages(out_path) as pdf:
        _cover_page(pdf, design,
                    "Plan + Profil en long — par sections",
                    A1_LANDSCAPE_IN, layouts)
        for name in layouts:
            fig = _render_layout_to_figure(doc, name, A1_LANDSCAPE_IN)
            pdf.savefig(fig)
            plt.close(fig)

    print(f"PDF generated: {out_path}  ({len(layouts)} pages + cover)")
    return out_path


def write_pt_pdf(dxf_path: Union[str, Path], out_path: Union[str, Path],
                 design: "RoadDesign") -> Path:
    """Render PT_001..PT_M to a multi-page A4-portrait PDF."""
    out_path = Path(out_path)
    doc = ezdxf.readfile(dxf_path)
    layouts = _pt_layouts(doc)

    with PdfPages(out_path) as pdf:
        _cover_page(pdf, design,
                    "Profils en travers",
                    A4_PORTRAIT_IN, layouts)
        for name in layouts:
            fig = _render_layout_to_figure(doc, name, A4_PORTRAIT_IN)
            pdf.savefig(fig)
            plt.close(fig)

    print(f"PDF generated: {out_path}  ({len(layouts)} pages + cover)")
    return out_path


# ─────────────────────────────────────────────────────────────────────────────
# In-memory variants (Streamlit download_button)
# ─────────────────────────────────────────────────────────────────────────────

def to_plan_pdf_bytes(dxf_path: Union[str, Path],
                      design: "RoadDesign") -> bytes:
    buf = io.BytesIO()
    doc = ezdxf.readfile(dxf_path)
    layouts = _plan_layouts(doc)
    with PdfPages(buf) as pdf:
        _cover_page(pdf, design,
                    "Plan + Profil en long — par sections",
                    A1_LANDSCAPE_IN, layouts)
        for name in layouts:
            fig = _render_layout_to_figure(doc, name, A1_LANDSCAPE_IN)
            pdf.savefig(fig)
            plt.close(fig)
    return buf.getvalue()


def to_pt_pdf_bytes(dxf_path: Union[str, Path],
                    design: "RoadDesign") -> bytes:
    buf = io.BytesIO()
    doc = ezdxf.readfile(dxf_path)
    layouts = _pt_layouts(doc)
    with PdfPages(buf) as pdf:
        _cover_page(pdf, design,
                    "Profils en travers",
                    A4_PORTRAIT_IN, layouts)
        for name in layouts:
            fig = _render_layout_to_figure(doc, name, A4_PORTRAIT_IN)
            pdf.savefig(fig)
            plt.close(fig)
    return buf.getvalue()
