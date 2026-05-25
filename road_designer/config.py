"""Design configuration for Road Designer V 1.0.

All design constants live here as a typed dataclass. **Never** introduce
module-level constants in business modules — accept a ``DesignConfig`` instead.

REFT presets cover Moroccan Recueil d'Études Techniques Fondamentales
categories 1 / 2 / 3. The default is REFT_CAT_1 (80-100 km/h rural main road).
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Optional


# ─────────────────────────────────────────────────────────────────────────────
# Sub-configs
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class TypicalSection:
    """Cross-section description (chaussée + accotements + fossés + talus)."""
    chaussee_width: float = 7.0          # m, total width of paved lanes
    crown_slope: float = 0.025           # 2.5 % crown (devers normal)
    accotement_width: float = 1.5        # m, each side
    accotement_slope: float = 0.04       # 4 %
    ditch_depth: float = 0.5             # m
    ditch_width: float = 1.0             # m
    talus_deblai_h_v: float = 2.0 / 3.0  # H/V — cut slope (default 2H:3V)
    talus_remblai_h_v: float = 3.0 / 2.0 # H/V — fill slope (default 3H:2V)


@dataclass
class CartoucheInfo:
    """Title-block fields. Filled per project via UI or CLI.

    ``company_name`` is mandatory — it appears as a professional header
    on every PDF page. The build will refuse to start if it is empty.
    """
    company_name: str = ""        # MANDATORY — header on every PDF page
    projet: str = ""
    maitre_ouvrage: str = ""
    bet: str = ""
    designer: str = ""
    plan_n: str = ""
    indice: str = "A"
    date: str = ""
    echelle_h: str = "1/1000"
    echelle_v: str = "1/100"


# ─────────────────────────────────────────────────────────────────────────────
# Main DesignConfig
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class DesignConfig:
    """Top-level config. Built by REFT presets or by the Streamlit UI."""

    # ── REFT category & speed ────────────────────────────────────────────
    design_speed: float = 90.0           # km/h
    road_category: str = "CAT_1"         # "CAT_1" | "CAT_2" | "CAT_3"

    # ── Horizontal alignment ─────────────────────────────────────────────
    road_width: float = 7.0              # total carriageway width [m]
    profile_sampling: float = 1.0        # dense sampling step along axis [m]

    # ── Vertical alignment (ligne rouge) — REFT minima for active category
    r_summit: float = 3000.0             # R_MIN_SOMMET_NORMAL — CAT 1
    r_sag: float = 1500.0                # R_MIN_CUVETTE_NORMAL — CAT 1
    max_radius: float = 6000.0           # cap on chosen vertical curve radius
    max_pente: float = 6.0               # % — absolute max grade
    min_tangent_length: float = 120.0    # m — min distance between two PVIs
    min_straight_tangent: float = 50.0   # m — min STRAIGHT length between
                                         #     two adjacent vertical curve
                                         #     ends (new in V 1.0, bug C6)
    max_grade_change: float = 0.005      # 0.5 % — PVI creation threshold on
                                         #         smoothed TN
    vertical_band_ratio: float = 0.13    # ± vertical band for SLSQP, fraction
                                         # of TN amplitude (ex-"smothing_factor"
                                         # — renamed, bug C4)
    safety_factor: float = 0.95          # fraction of available tangent
                                         # usable by a vertical curve

    # ── Drawing scales ───────────────────────────────────────────────────
    h_scale: float = 1.0                 # 1:1000 plan/profile horizontal
    v_scale: float = 10.0                # 1:100 profile vertical (×10 exag.)
    profile_gap_d: float = 100.0         # gap plan ↔ profile baseline [m]

    # ── Plan-view annotations ────────────────────────────────────────────
    cutting_line_length: float = 10.0
    annotation_offset: float = 15.0
    tick_length: float = 30.0
    tick_offset: float = 2.0
    arc_arrow_steps: int = 20
    arc_arrow_offset: float = 15.0
    straight_arrow_offset: float = 15.0
    # Multiplier applied to the profile-number bubble (radius + text height)
    # in both DXF modelspace and PDF plan pages. 1.5 = the BET-readable size
    # validated post V 1.0 launch.
    plan_bubble_scale: float = 1.5

    # ── Cubature / cross-section ─────────────────────────────────────────
    typical_section: TypicalSection = field(default_factory=TypicalSection)
    cross_section_step_pk: int = 1                 # every Nth station
    # ``cross_section_extent`` is the half-width sampled perpendicular to
    # the axis. ``None`` → 1.5 × road_width per side (total drawing width
    # = 3 × road_width), the BET convention for "vue en travers serrée".
    cross_section_extent: Optional[float] = None
    cross_section_scale_h: float = 100.0           # 1:100 H on PT sheets (DXF)
    cross_section_scale_v: float = 100.0           # 1:100 V on PT sheets (DXF)

    # ── Layout / paper ──────────────────────────────────────────────────
    sheet_length_pk: float = 500.0       # m per A1 sheet
    sheet_format: str = "A1"
    cartouche: CartoucheInfo = field(default_factory=CartoucheInfo)

    # ── Bruckner diagram (Step 5) ───────────────────────────────────────
    bruckner_row_height: float = 18.0    # vertical extent of the diagram [m]
    bruckner_v_scale: float = 0.002      # m³ → drawing unit (1 m³ = 0.002 m)

    # ── PDF scales (user-configurable, one set per PDF) ─────────────────
    # Denominators of 1:N. ``None`` means "use current default behaviour".
    #
    # Plan PDF: defaults preserve the auto-fit-to-page rendering the user
    # already validated. Set to e.g. ``1000`` / ``100`` to force exact
    # scales (drawing then sized in mm at the requested ratio).
    pdf_plan_h_scale: Optional[int] = None
    pdf_plan_v_scale: Optional[int] = None
    #
    # Profils en travers: defaults to **H 1:100  V 1:15** — the standard
    # BET detail scale on A4 portrait. With ``extent = 1.5 × road_width``
    # (= 21 m total for a 7 m chaussée) the drawing fills the A4 width.
    # Vertical exaggeration ≈ ×6.7 emphasises cut/fill while keeping the
    # typical-section break points readable. If the data is too tall
    # for A4 at V 1:15, the renderer scales the V axis down to fit and
    # reports the actually-achieved V scale in the footer.
    # Override either field with ``None`` to fall back to auto-picking.
    pdf_pt_h_scale: Optional[int] = 100      # 1:100
    pdf_pt_v_scale: Optional[int] = 25      # 1:25

    # ── Output filenames ────────────────────────────────────────────────
    dxf_filename: str = "road_design.dxf"
    xlsx_filename: str = "tableau_profil_en_long.xlsx"
    pdf_plan_filename: str = "plan_par_sections.pdf"  # Step 9 — one page per
                                                      # sheet_length_pk window
    pdf_pt_filename: str = "profils_en_travers.pdf"   # Step 9 — one page per PT
    pdf_dpi: int = 200                                 # render quality

    def to_dict(self) -> Dict[str, Any]:
        """JSON-serialisable snapshot — used by the Streamlit UI to remember
        the last session and by tests to pin a config."""
        return asdict(self)


# ─────────────────────────────────────────────────────────────────────────────
# REFT presets (Moroccan Recueil d'Études Techniques Fondamentales)
#
#   CAT 1 — 80-100 km/h    R_summit ≥ 3000, R_sag ≥ 1500, pente ≤ 6 %
#   CAT 2 — 60-80  km/h    R_summit ≥ 1500, R_sag ≥ 1000, pente ≤ 7 %
#   CAT 3 — 40-60  km/h    R_summit ≥ 750,  R_sag ≥ 500,  pente ≤ 8 %
#
# Values below match REFT "normal" minima (not absolute). For mountain or
# constrained sections the BET may relax to "absolute" minima — that decision
# is left to the engineer via the UI.
# ─────────────────────────────────────────────────────────────────────────────

REFT_CAT_1: DesignConfig = DesignConfig()  # defaults are CAT 1

REFT_CAT_2: DesignConfig = DesignConfig(
    design_speed=70.0,
    road_category="CAT_2",
    r_summit=1500.0,
    r_sag=1000.0,
    max_pente=7.0,
    min_tangent_length=100.0,
)

REFT_CAT_3: DesignConfig = DesignConfig(
    design_speed=50.0,
    road_category="CAT_3",
    r_summit=750.0,
    r_sag=500.0,
    max_pente=8.0,
    min_tangent_length=80.0,
    min_straight_tangent=30.0,
)


def get_preset(name: str) -> DesignConfig:
    """Lookup a REFT preset by name. Used by the Streamlit UI sidebar."""
    presets = {
        "CAT_1": REFT_CAT_1,
        "CAT_2": REFT_CAT_2,
        "CAT_3": REFT_CAT_3,
    }
    if name not in presets:
        raise ValueError(
            f"Unknown REFT preset '{name}'. Choose from {list(presets)}."
        )
    # Return a copy so the caller can mutate freely
    from copy import deepcopy
    return deepcopy(presets[name])
