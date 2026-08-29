// Mirrors backend/app/schemas.py — keep in sync by hand (the two frontends
// and the backend are separate deployables; see CLAUDE.md's three-surface
// architecture section).

export type RoadCategory = "CAT_1" | "CAT_2" | "CAT_3";

export interface TypicalSectionIn {
  crown_slope_pct: number;
  accotement_width: number;
  accotement_slope_pct: number;
  ditch_depth: number;
  ditch_width: number;
  talus_deblai_h_v: number;
  talus_remblai_h_v: number;
}

export interface CartoucheInfoIn {
  company_name: string;
  projet: string;
  maitre_ouvrage: string;
  bet: string;
  designer: string;
  plan_n: string;
  indice: string;
  date: string;
  echelle_h: string;
  echelle_v: string;
}

export interface SynthTerrainParams {
  z_base: number;
  slope_long: number;
  amplitude: number;
  wavelength: number;
  noise_sigma: number;
  extent: number;
  perp_step: number;
  pk_step: number;
  seed: number;
}

export interface DesignConfigIn {
  road_category: RoadCategory;
  road_width: number;
  profile_sampling: number;

  r_summit: number | null;
  r_sag: number | null;
  max_radius: number | null;
  max_pente: number | null;
  min_tangent_length: number | null;
  min_straight_tangent: number | null;
  max_grade_change: number | null;
  vertical_band_ratio: number | null;

  h_scale: number;
  v_scale: number;

  typical_section: TypicalSectionIn;
  cross_section_step_pk: number;
  cross_section_extent: number | null;

  sheet_length_pk: number;
  pdf_dpi: number;
  pdf_plan_h_scale: number | null;
  pdf_plan_v_scale: number | null;
  pdf_pt_h_scale: number | null;
  pdf_pt_v_scale: number | null;

  cartouche: CartoucheInfoIn;
  synth_terrain: SynthTerrainParams | null;
}

export type JobStatusValue = "queued" | "running" | "done" | "error";

export interface JobFiles {
  dxf: string;
  xlsx: string;
  pdf_plan: string;
  pdf_pt: string;
}

export interface JobStatus {
  job_id: string;
  status: JobStatusValue;
  files: JobFiles | null;
  warnings: string[] | null;
  error: string | null;
}

export interface PreviewPayload {
  plan: {
    axis: [number, number][];
    edges_left: [number, number][];
    edges_right: [number, number][];
  };
  profile: {
    pk: number[];
    tn: number[];
    projet: number[];
  };
  bruckner: {
    pk: number[];
    m: number[];
  };
}

// REFT presets — mirrors road_designer/config.py's REFT_CAT_1/2/3 defaults,
// used only to prefill the form; the backend re-derives the authoritative
// preset via get_preset(road_category) and only applies the fields the user
// actually touched (see DesignConfigIn.to_design_config in schemas.py).
export const REFT_PRESETS: Record<RoadCategory, {
  label: string;
  r_summit: number;
  r_sag: number;
  max_radius: number;
  max_pente: number;
  min_tangent_length: number;
  min_straight_tangent: number;
}> = {
  CAT_1: {
    label: "CAT 1 — 80-100 km/h",
    r_summit: 3000, r_sag: 1500, max_radius: 6000,
    max_pente: 6, min_tangent_length: 120, min_straight_tangent: 50,
  },
  CAT_2: {
    label: "CAT 2 — 60-80 km/h",
    r_summit: 1500, r_sag: 1000, max_radius: 6000,
    max_pente: 7, min_tangent_length: 100, min_straight_tangent: 50,
  },
  CAT_3: {
    label: "CAT 3 — 40-60 km/h",
    r_summit: 750, r_sag: 500, max_radius: 6000,
    max_pente: 8, min_tangent_length: 80, min_straight_tangent: 30,
  },
};

export function defaultDesignConfig(): DesignConfigIn {
  const p = REFT_PRESETS.CAT_1;
  return {
    road_category: "CAT_1",
    road_width: 7.0,
    profile_sampling: 1.0,
    r_summit: p.r_summit,
    r_sag: p.r_sag,
    max_radius: p.max_radius,
    max_pente: p.max_pente,
    min_tangent_length: p.min_tangent_length,
    min_straight_tangent: p.min_straight_tangent,
    max_grade_change: 0.005,
    vertical_band_ratio: 0.13,
    h_scale: 1.0,
    v_scale: 10.0,
    typical_section: {
      crown_slope_pct: 2.5,
      accotement_width: 1.5,
      accotement_slope_pct: 4.0,
      ditch_depth: 0.5,
      ditch_width: 1.0,
      talus_deblai_h_v: 2 / 3,
      talus_remblai_h_v: 3 / 2,
    },
    cross_section_step_pk: 1,
    cross_section_extent: null,
    sheet_length_pk: 500,
    pdf_dpi: 200,
    pdf_plan_h_scale: null,
    pdf_plan_v_scale: null,
    pdf_pt_h_scale: 100,
    pdf_pt_v_scale: 25,
    cartouche: {
      company_name: "",
      projet: "",
      maitre_ouvrage: "",
      bet: "",
      designer: "",
      plan_n: "PLAN",
      indice: "A",
      date: "",
      echelle_h: "1/1000",
      echelle_v: "1/100",
    },
    synth_terrain: null,
  };
}
