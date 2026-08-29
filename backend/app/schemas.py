"""Pydantic request/response models for the Road Designer API.

``DesignConfigIn`` mirrors the same ``DesignConfig`` surface the Streamlit
sidebar exposes (see ``frontends/streamlit/app.py``) — REFT category preset,
horizontal alignment, vertical-alignment minima, typical section / cubature
params, layout & PDF scale knobs, and the cartouche fields. It does not
reimplement validation the dataclass already encodes; it only carries user
input across the wire and converts it into a real ``road_designer.config.
DesignConfig`` via ``get_preset()`` + ``dataclasses.replace()``, exactly like
the Streamlit UI does.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from road_designer.config import CartoucheInfo, DesignConfig, TypicalSection, get_preset

RoadCategory = Literal["CAT_1", "CAT_2", "CAT_3"]


class TypicalSectionIn(BaseModel):
    crown_slope_pct: float = Field(2.5, description="Dévers normal, in %")
    accotement_width: float = 1.5
    accotement_slope_pct: float = Field(4.0, description="Pente accotement, in %")
    ditch_depth: float = 0.5
    ditch_width: float = 1.0
    talus_deblai_h_v: float = 2.0 / 3.0
    talus_remblai_h_v: float = 3.0 / 2.0


class CartoucheInfoIn(BaseModel):
    company_name: str = Field(..., description="Mandatory — header on every PDF page")
    projet: str = ""
    maitre_ouvrage: str = ""
    bet: str = ""
    designer: str = ""
    plan_n: str = "PLAN"
    indice: str = "A"
    date: str = ""
    echelle_h: str = "1/1000"
    echelle_v: str = "1/100"

    @field_validator("company_name")
    @classmethod
    def _company_name_required(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError(
                "cartouche.company_name is required (rendered as the header "
                "on every PDF page) — mirrors road_designer.build_design()'s "
                "own check."
            )
        return v.strip()


class SynthTerrainParams(BaseModel):
    """Optional synthetic-terrain generation params (used when no terrain
    file is uploaded). Mirrors ``road_designer.samples_api.generate_synthetic_terrain``."""
    z_base: float = 780.0
    slope_long: float = 0.02
    amplitude: float = 4.0
    wavelength: float = 600.0
    noise_sigma: float = 0.4
    extent: float = 60.0
    perp_step: float = 5.0
    pk_step: float = 5.0
    seed: int = 42


class DesignConfigIn(BaseModel):
    road_category: RoadCategory = "CAT_1"

    # Horizontal
    road_width: float = 7.0
    profile_sampling: float = 1.0

    # Vertical (REFT minima) — defaults overridden per-preset server-side
    r_summit: Optional[float] = None
    r_sag: Optional[float] = None
    max_radius: Optional[float] = None
    max_pente: Optional[float] = None
    min_tangent_length: Optional[float] = None
    min_straight_tangent: Optional[float] = None
    max_grade_change: Optional[float] = None
    vertical_band_ratio: Optional[float] = None

    # Drawing scales
    h_scale: float = 1.0
    v_scale: float = 10.0

    # Cross-section / cubature
    typical_section: TypicalSectionIn = Field(default_factory=TypicalSectionIn)
    cross_section_step_pk: int = 1
    cross_section_extent: Optional[float] = None

    # Layout / PDF scales
    sheet_length_pk: float = 500.0
    pdf_dpi: int = 200
    pdf_plan_h_scale: Optional[int] = None
    pdf_plan_v_scale: Optional[int] = None
    pdf_pt_h_scale: Optional[int] = 100
    pdf_pt_v_scale: Optional[int] = 25

    cartouche: CartoucheInfoIn

    # Terrain: either a file is uploaded (see the /designs multipart form),
    # or these synth params are used to generate one server-side.
    synth_terrain: Optional[SynthTerrainParams] = None

    def to_design_config(self) -> DesignConfig:
        base = get_preset(self.road_category)
        ts = TypicalSection(
            chaussee_width=self.road_width,
            crown_slope=self.typical_section.crown_slope_pct / 100.0,
            accotement_width=self.typical_section.accotement_width,
            accotement_slope=self.typical_section.accotement_slope_pct / 100.0,
            ditch_depth=self.typical_section.ditch_depth,
            ditch_width=self.typical_section.ditch_width,
            talus_deblai_h_v=self.typical_section.talus_deblai_h_v,
            talus_remblai_h_v=self.typical_section.talus_remblai_h_v,
        )
        cart = CartoucheInfo(
            company_name=self.cartouche.company_name,
            projet=self.cartouche.projet,
            maitre_ouvrage=self.cartouche.maitre_ouvrage,
            bet=self.cartouche.bet,
            designer=self.cartouche.designer,
            plan_n=self.cartouche.plan_n,
            indice=self.cartouche.indice,
            date=self.cartouche.date,
            echelle_h=self.cartouche.echelle_h,
            echelle_v=self.cartouche.echelle_v,
        )

        overrides = dict(
            road_width=self.road_width,
            profile_sampling=self.profile_sampling,
            h_scale=self.h_scale,
            v_scale=self.v_scale,
            cross_section_step_pk=self.cross_section_step_pk,
            cross_section_extent=self.cross_section_extent,
            sheet_length_pk=self.sheet_length_pk,
            pdf_dpi=self.pdf_dpi,
            pdf_plan_h_scale=self.pdf_plan_h_scale,
            pdf_plan_v_scale=self.pdf_plan_v_scale,
            pdf_pt_h_scale=self.pdf_pt_h_scale,
            pdf_pt_v_scale=self.pdf_pt_v_scale,
            typical_section=ts,
            cartouche=cart,
        )
        # Only override REFT minima when the caller actually set them —
        # otherwise keep the values from the chosen preset.
        for field_name in (
            "r_summit", "r_sag", "max_radius", "max_pente",
            "min_tangent_length", "min_straight_tangent",
            "max_grade_change", "vertical_band_ratio",
        ):
            value = getattr(self, field_name)
            if value is not None:
                overrides[field_name] = value

        return replace(base, **overrides)


class JobCreated(BaseModel):
    job_id: str
    status: Literal["queued"]


class JobFiles(BaseModel):
    dxf: str
    xlsx: str
    pdf_plan: str
    pdf_pt: str


class JobStatus(BaseModel):
    job_id: str
    status: Literal["queued", "running", "done", "error"]
    files: Optional[JobFiles] = None
    warnings: Optional[list[str]] = None
    error: Optional[str] = None
