# Road-Designer V 1.0

A Python application that produces BET-grade civil-engineering road-design deliverables (tracé en plan, profil en long, profils en travers, tableau, cubatures, diagramme de Bruckner, cartouches A1) from a terrain database and a horizontal alignment file.

Target user: a road-design civil engineer working in a Bureau d'Études Techniques (BET), Maghreb context, following Moroccan REFT standards (or equivalent ARP/ICTAAL). All on-drawing labels are in French.

Deployment: three independent surfaces share the one `road_designer/` engine — a Streamlit Community
Cloud app (`frontends/streamlit/`), a React SPA on Cloudflare Pages (`frontends/react/`) backed by a
FastAPI service on Hugging Face Spaces (`backend/`), and the local CLI (`python main.py`). See
[§ 15](#15-deployment-architecture--three-surfaces).

---

## Table of contents

1. [What the tool does](#1-what-the-tool-does)
2. [Vocabulary](#2-vocabulary)
3. [Repository layout](#3-repository-layout)
4. [Data flow](#4-data-flow)
5. [Module breakdown](#5-module-breakdown)
6. [DesignConfig — the configuration contract](#6-designconfig--the-configuration-contract)
7. [Core algorithms](#7-core-algorithms)
8. [DXF layer convention](#8-dxf-layer-convention)
9. [PDF rendering contract](#9-pdf-rendering-contract)
10. [Streamlit Cloud non-negotiables](#10-streamlit-cloud-non-negotiables)
11. [Conventions for future sessions](#11-conventions-for-future-sessions)
12. [Bug history (C1–C8 + Issues)](#12-bug-history-c1c8--issues)
13. [Roadmap status](#13-roadmap-status)
14. [Version](#14-version)
15. [Deployment architecture — three surfaces](#15-deployment-architecture--three-surfaces)

---

## 1. What the tool does

```
Inputs                                                       Outputs
─────────────────────────────────────────────────────        ─────────────────────────
terrain CSV  (X, Y, Z points)                                road_design.dxf
axe file     (segments droits D + courbes C: XC, YC, R)       • Tracé en plan
DesignConfig (REFT category, road width, talus, scales, …)    • Profil en long
cartouche    (company_name [mandatory], projet, BET, …)       • Tableau (7 rows)
                                                              • Pentes & rampes
       │                                                      • Curvature diagram
       ▼                                                      • Diagramme de Bruckner
                                                              • Paperspace layouts:
  RoadDesign ──► VerticalAlignment ──► cross_section.py         PLAN_xx (A1), PT_xx
       │                ↓                       ↓                with cartouche block
       │           SLSQP-optim                 polygon
       │           PVIs                        cut/fill        tableau_profil_en_long.xlsx
       │                                       areas             • 12 columns
       ▼                                                          • TOTAUX footer
  TerrainModel  (TIN + KDTree fallback)                           • REFT-warnings sheet
       │
       ▼                                                       plan_par_sections.pdf
  cubature.py    (average end-area + Bruckner)                  • A1 landscape, one
       │                                                          page per sheet_length_pk
       ▼                                                       profils_en_travers.pdf
  dxf_export.py + pdf_direct.py + excel_export.py               • A4 portrait, one
                                                                  page per cross-section
                                                                Both PDFs prepend a
                                                                **BET-cartouche-style
                                                                cover page** and carry a
                                                                **company-name header**
                                                                on every page.
```

The vertical alignment (ligne rouge) is **optimised** — not hand-traced. PVIs are placed where the smoothed TN curvature changes by more than `max_grade_change`, then SLSQP minimises `Σ |Z_projet − Z_TN|` over the dense PK grid, subject to three engineering constraints:

1. `|grade| ≤ max_pente` between every consecutive pair of PVIs.
2. Each parabolic curve must fit inside the available tangent: `L = R·|Δg|` ≤ `safety_factor × min(prev, next tangent)`.
3. The **straight portion** between the end of one curve (PVT) and the start of the next (PVC) must be at least `min_straight_tangent` metres.

Vertical curves are symmetric parabolas with a per-PVI radius (K-value): the **maximum feasible radius**, capped by `max_radius`, floored by REFT minimum for the curve type (`r_summit` for crest, `r_sag` for sag).

---

## 2. Vocabulary

| Term | Meaning |
|---|---|
| **PK** | Point Kilométrique — chainage along the axis, in metres. The primary independent variable for everything that isn't the plan view. |
| **Tracé en plan** | Plan view of the alignment (straights + arcs, sometimes clothoids). |
| **Profil en long** | Longitudinal profile — TN (ground) and projet (designed road) elevation vs PK. |
| **Profil en travers** | Cross-section — perpendicular slice at a given PK showing TN, chaussée, accotements, fossés, talus. |
| **Ligne rouge** | The vertical alignment of the projet (red line on the profile drawing). |
| **PVI** | Point of Vertical Intersection — where two tangent grades meet. Apex of each parabolic vertical curve. |
| **PVC / PVT** | Point of Vertical Curvature / Tangency — start and end of a vertical curve. |
| **K-value** | `K = L / |Δg|` (m per %). The code names this `R_SUMMIT` / `R_SAG`, treating R and K interchangeably. |
| **Sommet / Cuvette** | Summit (crest, Δg < 0) / sag (Δg > 0) vertical curve. |
| **Déblai / Remblai** | Cut / fill. Code abbreviates `Déb` / `Remb`. |
| **Cubature** | Earthwork volume (m³) between two consecutive cross-sections. |
| **Diagramme de Bruckner** | Mass-haul diagram: `M(PK) = Σ (V_remblai − V_déblai)` from origin to PK. |
| **Cartouche** | Title block on a paper sheet (project, BET, designer, échelle, n° de plan, indice, date). |
| **Dévers** | Superelevation — transverse slope of the chaussée in curves. |
| **REFT** | Recueil d'Études Techniques Fondamentales — Moroccan road design standard catalogue. |
| **BET** | Bureau d'Études Techniques — engineering consultancy that issues the deliverable. |
| **TN** | Terrain Naturel — existing ground surface. |
| **Tangente droite** | The straight portion of the ligne rouge between two vertical curves (between PVT_i and PVC_{i+1}). |

---

## 3. Repository layout

Current layout (everything below is committed). See [§ 15](#15-deployment-architecture--three-surfaces)
for how `backend/` and `frontends/` fit into the three-surface deployment story.

```
Road_designe/
├── CLAUDE.md                      ← this file (V 1.0 reference for future sessions)
├── AGENTS.md                      ← same content, for non-Claude agents
├── README.md / README.fr.md       ← user-facing intro (English default + French, language nav at top)
├── DEPLOYMENT.md                  ← beginner-oriented step-by-step deploy guide (see § 15)
├── LICENSE NOTICE THIRD-PARTY-NOTICES.md LICENSING.md CONTRIBUTING.md
│                                  ← Beamstack Community License 1.0 + attribution / contributor terms (see § 11)
├── brand/                         ← Beamstack logo + usage rules for the attribution mark
├── Dockerfile                    ← backend image; build context = repo root; listens on ${PORT:-7860}
├── .dockerignore / .gcloudignore  ← keep the backend build context / Cloud Build upload small
├── requirements.txt               ← pinned, Python 3.12 target (engine + CLI + Streamlit)
├── .gitignore                     ← *.dxf, *.xlsx, *.pdf, Road_venv/, .venv/, output/
├── .github/
│   └── workflows/
│       └── keep-alive-backend.yml ← optional cron ping (BACKEND_HEALTH_URL secret); HF/Render/Koyeb only, NOT Cloud Run
│
├── main.py                        ← CLI entry point (unchanged)
│
├── road_designer/                 ← installable package (the engine — see constraints in § 15)
│   ├── __init__.py                ← public API exports
│   ├── config.py                  ← @dataclass DesignConfig + REFT_CAT_1/2/3
│   ├── mnt_engine.py              ← TerrainModel (TIN + KDTree fallback)
│   ├── axe_parser.py              ← LineSegment, ArcSegment, AlignmentParser
│   ├── geometry_engine.py         ← normal, offset, rotation primitives
│   ├── design_logic.py            ← VerticalAlignment (parabolic curves)
│   ├── road_design.py             ← RoadDesign orchestrator + build_design()
│   ├── cubature.py                ← per-segment volumes + Bruckner curve
│   ├── cross_section.py           ← TypicalSection + per-PK section + cut/fill polygons
│   ├── dxf_export.py              ← DXF assembly (modelspace + paperspace)
│   ├── pdf_direct.py              ← direct-matplotlib PDF (replaces pdf_export.py)
│   ├── pdf_export.py              ← legacy ezdxf-based PDF (kept for backward compat)
│   ├── excel_export.py            ← XLSX/CSV writers
│   └── samples_api.py             ← sample-file paths + synthetic-terrain wrapper
│
├── samples/                       ← shipped sample data (gitignored exceptions)
│   ├── sample_axe.txt
│   ├── sample_terrain.csv
│   └── synth_terrain.py           ← synthetic-terrain generator (CLI + lib)
│
├── docs/
│   ├── INPUT_FORMAT.md            ← axe + CSV grammar with annotated example
│   └── LINKEDIN_POST.md           ← marketing copy for the V 1.0 launch
│
├── tests/                         ← pytest suite (engine tests, unchanged by the frontend work)
│   ├── conftest.py                ← shared fixtures (axe_path, terrain_path, design)
│   ├── test_axe_parser.py         ← D+C grammar, station continuity, sampling
│   ├── test_vertical_alignment.py ← parabolic continuity, REFT floor, C6
│   ├── test_cubature.py           ← area sign, h=0 split, balance, Bruckner
│   ├── test_geometry.py           ← normal, offset, rotation round-trip
│   ├── test_layout.py             ← profile-below-plan, monotonic PK, V scale
│   └── test_pdf_contract.py       ← company_name required, PT scale picker, vertical grids
│
├── output/                        ← gitignored, local CLI dumps here
│
├── backend/                       ← FastAPI app (deploys to Google Cloud Run; HF Spaces is the documented alt)
│   ├── app/
│   │   ├── main.py                ← FastAPI() instance, CORS via ALLOWED_ORIGIN env var, lifespan cleanup
│   │   ├── schemas.py             ← Pydantic mirrors of DesignConfig/TypicalSection/CartoucheInfo
│   │   ├── jobs.py                ← in-memory job store + ThreadPoolExecutor runner, 30-min TTL sweep
│   │   └── routers/
│   │       ├── designs.py         ← POST /designs, GET /designs/{id}, GET /designs/{id}/files/{kind}
│   │       ├── preview.py         ← GET /designs/{id}/preview (plan/profile/Bruckner JSON for the SPA)
│   │       └── health.py          ← GET /health (also pinged by the optional keep-alive workflow)
│   ├── requirements.txt           ← fastapi/uvicorn/pydantic + engine deps, pinned; no streamlit
│   └── tests/                     ← pytest + httpx, reuses tests/conftest.py's fixtures
│   (the backend Docker image is built from the repo-root Dockerfile above)
│
└── frontends/
    ├── streamlit/                 ← MOVED from repo root (git mv), behavior unchanged
    │   ├── app.py                 ← sys.path fixed up to resolve the repo root + docs/ path
    │   └── .streamlit/
    │       └── config.toml        ← maxUploadSize = 20 MB, light theme
    │
    └── react/                     ← NEW — Vite + React + TypeScript + Tailwind (deploys to Cloudflare Pages)
        ├── src/                    ← DesignForm, JobStatusPanel, PreviewPanel, from-scratch SVG chart
        ├── package.json
        ├── wrangler.toml           ← Cloudflare Pages config (optional CLI-deploy path)
        └── .env.example            ← VITE_API_BASE_URL placeholder (build-time only, see § 15)
```

---

## 4. Data flow

```
       ┌──────────────────┐   parse    ┌────────────────────┐
       │   axe.txt        │ ─────────► │  AlignmentParser   │──┐
       └──────────────────┘            └────────────────────┘  │
                                                                │ segments[]
                                                                │ station_points[]
       ┌──────────────────┐   load     ┌────────────────────┐  │
       │ terrain_db.csv   │ ─────────► │   TerrainModel     │  │
       └──────────────────┘            │  (TIN + KDTree)    │  │
                                       └────────────────────┘  │
                                                  ▲             │
                                                  │ query_z(x,y)│
                                                  │             ▼
                                       ┌─────────────────────────────────┐
                                       │           RoadDesign            │
                                       │                                 │
                                       │ 1. station_vertices (PK,X,Y)    │
                                       │ 2. plan rotation start→end      │
                                       │ 3. dense sampling of axis       │
                                       │ 4. TN at every dense PK         │
                                       │ 5. generate_optimized_pvis()    │
                                       │       └─SLSQP w/ constraints    │
                                       │ 6. VerticalAlignment(pvis,…)    │
                                       │ 7. Z_projet at every PK         │
                                       └────────────┬───────────┬────────┘
                                                    │           │
                                                    ▼           ▼
                                       ┌───────────────────┐  ┌────────────────┐
                                       │  cross_section.py │  │  cubature.py   │
                                       │   per-PK section  │  │  (consumes the │
                                       │   + cut/fill      │  │   per-PK cut & │
                                       │   polygons        │  │   fill areas)  │
                                       └────────┬──────────┘  └────────┬───────┘
                                                │                      │
                ┌───────────────────────────────┴──────┬───────────────┘
                ▼                                      ▼
      ┌──────────────────┐                ┌────────────────────────┐
      │   dxf_export.py  │                │     pdf_direct.py      │
      │ • modelspace     │                │ • cover (BET cartouche)│
      │ • PLAN_xx (A1)   │                │ • plan_par_sections.pdf│
      │ • PT_xx (A4)     │                │ • profils_en_travers.pdf│
      └──────────────────┘                └────────────────────────┘
                │
                ▼
      ┌──────────────────┐
      │ excel_export.py  │
      │ • 12 columns     │
      │ • TOTAUX footer  │
      │ • REFT warnings  │
      └──────────────────┘
```

Single entry point: `road_designer.road_design.build_design(cfg, axe_path, terrain_path, out_dir) → dict`. Used by both `main.py` (CLI) and `app.py` (Streamlit).

---

## 5. Module breakdown

### `road_designer/config.py` (≈ 200 lines)

Three dataclasses:

- **`TypicalSection`** — cross-section description: chaussée width, crown slope, accotement width/slope, ditch depth/width, talus H/V for cut and fill.
- **`CartoucheInfo`** — title-block fields. `company_name` is mandatory; the build refuses to start if it is empty (validated in `build_design`).
- **`DesignConfig`** — top-level config. Holds REFT category & speed, horizontal alignment params, vertical alignment minima + the new `min_straight_tangent` and the renamed `vertical_band_ratio` (the ex-`smothing_factor` typo), drawing scales, plan-view annotation sizes, cross-section settings (with `cross_section_extent: Optional[float] = None` resolving to `1.5 × road_width`), Bruckner row sizing, paperspace layout, embedded `CartoucheInfo`, and the four PDF scale knobs.

Three preset constants:

- **`REFT_CAT_1`** = `DesignConfig()` defaults — 80–100 km/h, R_summit ≥ 3000, R_sag ≥ 1500, max_pente = 6 %.
- **`REFT_CAT_2`** — 60–80 km/h, R_summit ≥ 1500, R_sag ≥ 1000, max_pente = 7 %.
- **`REFT_CAT_3`** — 40–60 km/h, R_summit ≥ 750, R_sag ≥ 500, max_pente = 8 %.

`get_preset(name)` returns a deep copy so callers can mutate freely.

### `road_designer/mnt_engine.py` (≈ 55 lines)

`TerrainModel(csv_path)`:
- Loads a CSV with `X, Y, Z` columns (raises `ValueError` if missing).
- Builds a Delaunay TIN with `scipy.interpolate.LinearNDInterpolator`.
- Builds a `scipy.spatial.cKDTree` for nearest-neighbour fallback.
- `query_z(x, y)` returns the TIN-interpolated Z, falling back to NN with a one-time warning per out-of-hull query.
- `bounds` returns the point-cloud envelope.

### `road_designer/axe_parser.py` (≈ 230 lines)

Two segment classes and a parser:

- **`LineSegment(start, end, start_pk, end_pk)`** — straight; `point_at_distance(d)`, `direction_at_distance(d)`, `normal_at_distance(d)`.
- **`ArcSegment(start, end, center, radius, start_pk, end_pk, length)`** — circular arc; signed radius (positive = left turn, negative = right turn). The sweep angle is recovered from cross/dot of the start/end radial vectors; a warning is emitted if the computed arc length disagrees with the given length by more than 0.1 m.
- **`AlignmentParser(filename).parse()`** — reads a Moroccan-style axe file. First line is `PK0 X0 Y0`. Then repeating `D{n}` (straight) or `C{n}` (curve with `XC`, `YC`, `R` lines) blocks, each terminated by the end station.
- **`sample_points(step)`** — dense PK-uniform sampling along all segments. The last sample of each segment is **anchored to `seg.end_pk`** to prevent sub-mm non-monotonicities at segment boundaries (regression test pins this).

### `road_designer/geometry_engine.py` (≈ 55 lines)

Pure NumPy helpers used by plan rendering and cross-section sampling:
- `compute_normal(dx, dy)` — unit left-hand normal.
- `offset_points(axis, road_width)` — left/right edge polylines.
- `cutting_line_points(axis_point, normal, length)` — endpoints of a cross-section indicator.
- `rotate_points(points, angle)` / `rotate_vector(v, angle)` — 2D rotations.

### `road_designer/design_logic.py` (≈ 155 lines)

`VerticalAlignment(pvi_list, min_summit, min_sag, safety_factor=0.95, target_mode="max", max_radius=None)`:
- `_compute_curves()` walks consecutive grade pairs, picks per-PVI radius:
  - `R_max = safety_factor × min(prev_tangent, next_tangent) / |Δg|`
  - `R = max(R_max, REFT_minimum)` — floored, with a warning when REFT min wins.
- `get_z(pk)` returns the projet elevation. Inside a curve it evaluates the parabola `y = y_PVC + g1·x + (g2−g1)/(2L) · x²`; on a tangent it does linear interpolation between PVIs; outside the alignment it clamps to the endpoints.
- `check_curve_overlap(min_straight_tangent)` — returns a list of human-readable warnings when adjacent curves leave less than `min_straight_tangent` of actual straight between them. Used by the build to surface C6 violations in the XLSX REFT-warnings sheet.

### `road_designer/road_design.py` (≈ 470 lines)

The orchestrator. `RoadDesign(terrain_csv, axe_txt, cfg)`:
1. Parses axe + loads terrain.
2. Computes the plan rotation (`road_angle = atan2(dy, dx)` from start to end) — drawing-only; never propagates to PK math.
3. Builds the **PK-based axis X** (`pk_axis_x = (vert_pks − pk0) × h_scale`) — the C1/C2 fix.
4. Samples TN at every dense PK.
5. Runs `generate_optimized_pvis()` — picks PVI candidates from a smoothed TN (UnivariateSpline) where curvature exceeds `max_grade_change`, then SLSQP-optimises their elevations under the three constraints.
6. Builds the `VerticalAlignment`, surfaces C6 warnings via `check_curve_overlap`.
7. Computes `vert_proj_z` via `v_align.get_z(pk)` at every station (C2 fix — never interpolate the rotated-X profile line).
8. Provides public APIs: `get_plan_axis`, `get_plan_edges`, `get_arc_annotations`, `get_line_annotations`, `get_profile_data`, `get_rappel_segments`, `get_table_data`. The table's `col_x` is the PK-based X (C1), `cote_proj` is recomputed from `v_align.get_z` (C2).

`build_design(cfg, axe_path, terrain_path, out_dir)`:
- Validates `cfg.cartouche.company_name` is non-empty (raises `ValueError` otherwise).
- Builds the design.
- Computes cross-sections with `all_sections(design)` (Step 7).
- Computes cubatures with `compute_cubatures(design)` — automatically uses the polygon-true areas (Step 7b) because `design.section_areas` is now populated.
- Writes DXF, XLSX, plan PDF, PT PDF.
- Returns `{dxf, xlsx, pdf_plan, pdf_pt, warnings}`.

### `road_designer/cubature.py` (≈ 190 lines)

Three exports:

- **`area_plateforme(h, road_width, m_deb, m_rem)`** — fallback signed area `h × (W + |h|×m)`, used when no polygon area is available.
- **`_segment_volume(h1, h2, a1, a2, dpk)`** — returns `(V_deb, V_rem)` for one segment using the **moyenne des aires** method. **Critically:** when `h1` and `h2` have opposite signs, the segment is **split at the h = 0 crossing** so cut and fill are not mixed in the same average — without this, Bruckner extrema are smeared.
- **`compute_cubatures(design)`** — returns a `CubatureResult` (h per vertex, signed area per vertex, V_deb/V_rem per segment + cumulative, `bruckner = V_rem_cum − V_deb_cum`, totals, balance). When `design.section_areas` is populated by `cross_section.py`, the **signed polygon area** `fill_area − cut_area` from the actual cross-section polygon replaces the plateforme approximation per PK (the Step 7b swap).

### `road_designer/cross_section.py` (≈ 330 lines)

Two dataclasses and three helpers:

- **`CrossSectionResult`** — `pk`, `tn_polyline [(t, z)]`, `proj_polyline [(t, z)]`, `cut_polygons`, `fill_polygons`, `cut_area`, `fill_area`, `z_axis_proj`, `z_axis_tn`, `projet_break_points [(t, z, label)]`.
- **`build_projet_polyline(ts, z_axis)`** — full projet polyline from the `TypicalSection`: axis → chaussée (with crown slope) → accotement → ditch (triangular: berge → fond → berge) symmetrically left/right.
- **`_extend_talus(t_start, z_start, side, hv_ratio, going_down, tn_t, tn_z, max_extent)`** — extends the talus outward from the outer ditch berge until it meets TN. Uses a sign-change scan on the parametric `(t, z)` of the talus minus TN-interpolated at `t`. Falls back to the extent endpoint when no crossing is found in `max_extent` metres.
- **`_cut_fill_polygons(tn_t, tn_z, proj_t, proj_z)`** — merges the t-grids of TN and projet, walks groups of same-sign `h = z_pj − z_tn`, **inserts zero-crossings** at boundaries, returns ordered polygons (projet → TN reversed) for each group. Areas computed via shoelace.
- **`section_at_pk(design, pk)`** — assembles the whole thing: finds the axis point and tangent at `pk`, samples TN perpendicularly on `±extent` (where `extent = cfg.cross_section_extent or 1.5 × cfg.road_width`), builds projet, closes talus, computes polygons + areas.
- **`all_sections(design)`** — one section per station vertex (filtered by `cfg.cross_section_step_pk`).

### `road_designer/dxf_export.py` (≈ 1050 lines)

`write_dxf(design, out_path)` builds the DXF in this order:
1. **Modelspace plan** — axis, edges, arc + straight annotations with ticks, cutting lines, profile-number bubbles.
2. **Modelspace profile** — TN polyline (dense), projet polyline (dense), cut/fill labels (`Remb=…m`, `Déb=…m`) rotated 45°, vertical guides linking each profile vertex down to the top of the table (perfectly vertical because `pk_axis_x` is shared — the Issue 1 fix).
3. **Modelspace table** — 7 rows (Profil n° / Distance Partielle / Distance Cumulée / Cote TN / Cote Projet / Pente / Cubatures Déb/Remb), title column on the left, totals box on the right. Rows 2/3/4 have a height of 21.0 drawing units (the user-requested ×1.4 over the original 15) so rotated-90° text fits.
4. **Modelspace curvature diagram** — bumps for each parabolic curve + slope-and-length labels for straights.
5. **Modelspace Bruckner** — mass-haul curve below the curvature diagram, baseline at M=0, dashed leaders at local extrema, balance verdict ("Excédent → évacuer" / "Déficit → emprunter").
6. **Paperspace `PT_001..PT_M`** — one A4 portrait layout per cross-section (Step 7).
7. **Paperspace `PLAN_01..PLAN_N`** — one A1 landscape layout per `cfg.sheet_length_pk` window with a CARTOUCHE block (Step 8).

The 24-entry `LAYERS` dict at the top of the module is the single source of truth for layer names + colour indices.

### `road_designer/pdf_direct.py` (≈ 1050 lines)

The current PDF renderer. **Does not round-trip through `ezdxf.addons.drawing`** — that backend was slow and dropped labels. Instead, it draws every page directly from `RoadDesign` data using matplotlib primitives. Vector output, infinite zoom, true text fidelity.

Key entry points:
- `write_plan_pdf(_, out_path, design)` and `to_plan_pdf_bytes(_, design)` — A1 landscape, one page per `cfg.sheet_length_pk` window. Each page has: company header band → plan view (top half, rotated coords) → profile + 7-row table + grade diagram band + Bruckner band (bottom half, PK coords with perfectly-vertical guides).
- `write_pt_pdf(_, out_path, design)` and `to_pt_pdf_bytes(_, design)` — A4 portrait, one page per cross-section. Each page has: company header → "Profil en travers PK …" title + axis cotes stats → drawing area (centred horizontally, anchored near the top) → footer with cut/fill areas + scales label.
- `_cover_page(pdf, design, title, page_size_in, n_pages)` — **the professional BET-cartouche-style cover**: large company name at top with red accent line → "DOSSIER DE PROJET" pill badge → project-title box → INFORMATIONS PROJET grid → CUBATURES box with horizontal bar chart → 4-cell footer strip (N° plan / Indice / Date / Pages) → footer line. Sizing adapts to A4 vs A1.
- `_draw_company_header(fig, design, page_title, page_n, page_total)` — top-of-page band on every non-cover page: company name (bold left), project + indice (centered), document title + page n/N + date (right), thin red separator.

PT scale resolution — `_pick_pt_scales(t_range, z_range, user_scale_h, user_scale_v)`:
- If user provides `user_scale_h`, use it verbatim; else pick the smallest scale from `[20, 25, 50, 100, 125, 150, 200, 250, 300, 400, 500, 750, 1000, 1500, 2000]` whose data span fits `_PT_DRAW_W_MM`.
- If user provides `user_scale_v`, use it verbatim; else `scale_v = scale_h` (1:1 ratio — default for the picker mode).
- Returns `(scale_h, scale_v, width_mm, height_mm)`.

Auto-cap (in `_render_pt_page`): if the user-forced scales produce a drawing bigger than the A4 useable body (`_PT_DRAW_W_MM = 200` × `_PT_DRAW_H_MM = 235` mm), the renderer ratchets the affected axis to fit and prepends `(échelle ajustée pour A4)` to the footer scales label.

### `road_designer/excel_export.py` (≈ 150 lines)

- `to_dataframe(design)` — 12 columns: Profil, PK, Distance Partielle, Cote TN, Cote Projet, h, Pente entrante, V Déblai segment, V Remblai segment, V Déblai cumulé, V Remblai cumulé, Bruckner M(PK).
- `write_xlsx(design, path)` — openpyxl writer, frozen header, auto-widened columns, TOTAUX footer (Σ Déblai, Σ Remblai, Bilan), platform-mode note. Second sheet "Avertissements REFT" lists every `tangent_warning` from the design.
- `write_csv(design, path)` — UTF-8-BOM, semicolon-separated, Excel-FR-friendly.
- `to_xlsx_bytes(design)` — in-memory variant for the Streamlit downloader.

### `road_designer/samples_api.py` (≈ 80 lines)

- `sample_axe_path()` / `sample_terrain_path()` — `Path` objects to the bundled samples.
- `sample_axe_bytes()` / `sample_terrain_bytes()` — for the Streamlit UI when streaming to a tempdir.
- `generate_synthetic_terrain(axe_path, out_path, **synth_kwargs)` — wraps `samples/synth_terrain.generate`.
- `synthetic_terrain_bytes(axe_path, **kwargs)` — in-memory CSV bytes for download.

### Top-level entry points

- **`main.py`** — `argparse` CLI: `--axe`, `--terrain`, `--out`, `--category`, `--company` (required), `--projet`, `--designer`. Defaults to bundled samples.
- **`app.py`** — Streamlit UI. Sidebar groups: 1. Données d'entrée (sample / upload / synthetic) → 2. Catégorie REFT → 3. Paramètres de conception (Géométrie horizontale, Ligne rouge, Section type, Mise en page / PDF, Cartouche). Tabs: Calcul + téléchargements (4 download buttons), Tableau (st.dataframe of the XLSX), Aperçus (matplotlib previews of profile + Bruckner), Aide (rendered `docs/INPUT_FORMAT.md`). Generate button is **disabled until `company_name` is filled**.

---

## 6. DesignConfig — the configuration contract

```python
@dataclass
class TypicalSection:
    chaussee_width:   float = 7.0
    crown_slope:      float = 0.025
    accotement_width: float = 1.5
    accotement_slope: float = 0.04
    ditch_depth:      float = 0.5
    ditch_width:      float = 1.0
    talus_deblai_h_v: float = 2/3
    talus_remblai_h_v:float = 3/2

@dataclass
class CartoucheInfo:
    company_name:    str = ""        # MANDATORY — refused if empty
    projet:          str = ""
    maitre_ouvrage:  str = ""
    bet:             str = ""
    designer:        str = ""
    plan_n:          str = ""
    indice:          str = "A"
    date:            str = ""
    echelle_h:       str = "1/1000"
    echelle_v:       str = "1/100"

@dataclass
class DesignConfig:
    # REFT category & speed
    design_speed:           float = 90.0
    road_category:          str   = "CAT_1"

    # Horizontal
    road_width:             float = 7.0
    profile_sampling:       float = 1.0

    # Vertical (REFT minima)
    r_summit:               float = 3000.0
    r_sag:                  float = 1500.0
    max_radius:             float = 6000.0
    max_pente:              float = 6.0
    min_tangent_length:     float = 120.0    # min distance between PVIs
    min_straight_tangent:   float = 50.0     # min STRAIGHT between curve ends (C6)
    max_grade_change:       float = 0.005
    vertical_band_ratio:    float = 0.13     # (was the typo'd smothing_factor)
    safety_factor:          float = 0.95

    # Drawing scales (DXF modelspace)
    h_scale:                float = 1.0
    v_scale:                float = 10.0
    profile_gap_d:          float = 100.0

    # Plan-view annotation sizes
    cutting_line_length:    float = 10.0
    annotation_offset:      float = 15.0
    tick_length:            float = 30.0
    tick_offset:            float = 2.0
    arc_arrow_steps:        int   = 20
    arc_arrow_offset:       float = 15.0
    straight_arrow_offset:  float = 15.0

    # Cross-section
    typical_section:        TypicalSection = field(default_factory=TypicalSection)
    cross_section_step_pk:  int             = 1
    cross_section_extent:   Optional[float] = None   # None → 1.5 × road_width
    cross_section_scale_h:  float           = 100.0
    cross_section_scale_v:  float           = 100.0

    # Layout / paper
    sheet_length_pk:        float = 500.0
    sheet_format:           str   = "A1"
    cartouche:              CartoucheInfo = field(default_factory=CartoucheInfo)

    # Bruckner band
    bruckner_row_height:    float = 18.0
    bruckner_v_scale:       float = 0.002   # m³ → drawing unit

    # PDF scales (configurable per PDF, both fields per PDF)
    pdf_plan_h_scale:       Optional[int] = None   # None = auto-fit (current look)
    pdf_plan_v_scale:       Optional[int] = None
    pdf_pt_h_scale:         Optional[int] = 100    # default 1:100 (A4 portrait)
    pdf_pt_v_scale:         Optional[int] = 25     # default 1:25  (×4 exag)

    # Output filenames
    dxf_filename:           str = "road_design.dxf"
    xlsx_filename:          str = "tableau_profil_en_long.xlsx"
    pdf_plan_filename:      str = "plan_par_sections.pdf"
    pdf_pt_filename:        str = "profils_en_travers.pdf"
    pdf_dpi:                int = 200
```

**Rule for future edits:** any new design constant goes here. **Never** introduce module-level constants in business modules; accept a `DesignConfig` instance instead. Subdictionaries that need different defaults per REFT category go in the category-specific preset.

---

## 7. Core algorithms

### 7.1 PVI optimisation (SLSQP)

In `RoadDesign.generate_optimized_pvis()`:

1. **PVI placement** — Smooth the TN samples with `UnivariateSpline(s = vertical_band_ratio × N)`. Walk station-by-station, pick a PVI at every station where the smoothed grade-in vs grade-out difference exceeds `max_grade_change`, subject to a minimum spacing of `min_tangent_length`.
2. **Initial elevations** — Each PVI's Z is initially the spline-smoothed TN at its PK.
3. **Bounds** — Each Z can move within `± vertical_band_ratio × (Z_max − Z_min)` (the user can widen this to escape local minima).
4. **Objective** — `Σ |v_align.get_z(pk) − z_tn(pk)|` summed over the dense PK grid. The temporary `VerticalAlignment` is rebuilt inside the objective (the cost SciPy pays per iteration).
5. **Constraints** — three inequality constraints (`'type': 'ineq'` means "must be ≥ 0"):
   - Grade per inter-PVI segment ≤ `max_pente`.
   - Curve length needed at PVI `i` ≤ available tangent (with `safety_factor`).
   - Straight tangent between curves `i` and `i+1` ≥ `min_straight_tangent` (C6).
6. **Solver** — SciPy SLSQP, `maxiter = 500`. The solver may report "Inequality constraints incompatible" on tight datasets; we still take its best result and surface a `tangent_warning` to the XLSX. The drawing stays usable.

### 7.2 Parabolic vertical curve

For each interior PVI `i`:
- `Δg = grades[i] − grades[i−1]` (positive ⇒ cuvette, negative ⇒ sommet).
- `R_max = safety_factor × min(dist_prev, dist_next) / |Δg|`.
- `R = min(R_max, max_radius)`. If `R < REFT_min` (where REFT min is `r_summit` or `r_sag` depending on sign), `R` is floored to the REFT minimum and a warning is emitted.
- `L = R × |Δg|`. Curve spans `[pvi_pk − L/2, pvi_pk + L/2]`.
- Inside the curve, `get_z(pk)`:
  ```
  x  = pk − PVC_pk
  y_PVC = pvi_z − (g1 × L/2)
  z(pk) = y_PVC + g1·x + ((g2 − g1) / (2L)) · x²
  ```
- Outside curves, linear interpolation between PVIs; outside the alignment, clamp to endpoint.

### 7.3 Cubature (average end-area with h = 0 split)

For each pair of consecutive station vertices `(pk_i, pk_{i+1})`:
- Resolve cross-section areas: if `design.section_areas[pk]` exists, use the **polygon signed area** `fill_area − cut_area`; otherwise use the **plateforme** approximation `h × (W + |h|·m)` where `m` is the talus ratio (déblai or remblai depending on sign of `h`).
- Volume = `½ × (a_i + a_{i+1}) × Δpk`.
- **Sign handling** — when `h_i` and `h_{i+1}` have opposite signs, find the zero-crossing fraction `t = h_i / (h_i − h_{i+1})` and split the segment at that point. The part before the zero is one category (cut or fill), the part after is the other. Without this split, every transition mixes cut and fill in a single segment and the Bruckner diagram loses its physical meaning.
- Build `V_deb_cum`, `V_rem_cum`, `bruckner = V_rem_cum − V_deb_cum`, totals and balance.

### 7.4 Cross-section assembly

For each PK in `all_sections`:
1. Axis point and tangent: walk `design.segments`, find the segment whose PK range contains `pk`, evaluate `seg.point_at_distance(d)` and `seg.direction_at_distance(d)` where `d = pk − seg.start_pk`.
2. TN sampling along the perpendicular: 60 + samples at `± extent` metres, calling `terrain.query_z` at each.
3. Projet polyline from `TypicalSection`: axis → bord chaussée (with crown slope) → bord accotement → fond fossé → berge fossé. Symmetric left/right.
4. Talus closure: extend a parametric line at slope `H/V` from each outer berge until it crosses TN (or until `max_extent` is reached).
5. Cut/fill polygons: merge the TN and projet t-grids, classify each interval by `sign(z_pj − z_tn)`, insert zero-crossings, build closed polygons (projet on top, TN reversed below), shoelace area.

### 7.5 PDF page sizing

**Plan PDF** (`_render_plan_page`, `_plan_h_geometry`):
- If `cfg.pdf_plan_h_scale` is set, the plan/profile axes are sized so that 1 m on the road = `1000 / pdf_plan_h_scale` mm on paper. Centred on the A1 sheet, capped to 95 % of page width.
- If `None`, fit-to-page (`left = 0.04`, `width = 0.92`) — the historical look.

**PT PDF** (`_render_pt_page` + `_pick_pt_scales`):
- Pick scales from user-forced or auto-picked.
- Compute `w_mm`, `h_mm` from data ranges and chosen scales.
- **Auto-cap**: if `w_mm > _PT_DRAW_W_MM` (200) or `h_mm > _PT_DRAW_H_MM` (235), ratchet the affected scale down to fit and mark the footer with `(échelle ajustée pour A4)`.
- Place the axes horizontally centred on the page, top-anchored just below the title block.

---

## 8. DXF layer convention

| Layer | Colour | Used for |
|---|---|---|
| `AXIS` | 5 (blue) | Centreline polyline |
| `EDGES` | 8 (grey) | Road edges in plan |
| `GROUND` | 3 (green) | TN polyline on profile |
| `PROJECT` | 1 (red) | Projet (ligne rouge) polyline on profile |
| `RAPPEL` | 2 (yellow, DASHED) | Vertical guides profile ↔ table (Issue 1) |
| `HAUTEURS_REM` | 3 | `Remb=…m` labels |
| `HAUTEURS_DEB` | 1 | `Déb=…m` labels |
| `TABLE` | 7 | Table frame lines |
| `TABLE_TEXT` | 7 | Table cell text |
| `TABLE_CUBATURE` | 6 | 7th-row cubature text (D / R per segment) |
| `BUBBLES` | 4 (cyan) | Profile-number bubbles |
| `CUTTING_LINES` | 6 | Cross-section indicators on plan |
| `TICKS` | 6 | Arc endpoint ticks |
| `ARC_ARROW` | 4 | Curved arrow + `R=… L=…` label |
| `STRAIGHT_ARROW` | 4 | Straight segment length arrow |
| `CURV_DIAG` | 7 | Curvature-diagram frame & text |
| `CURV_DIAG_PROJ` | 1 | Sloped tangent lines in curvature row |
| `CURV_DIAG_ARC` | 4 | Parabolic bumps in curvature row |
| `BRUCKNER` | 6 | Mass-haul curve |
| `BRUCKNER_BASE` | 7 | Baseline + frame |
| `BRUCKNER_TEXT` | 7 | Bruckner labels |
| `PT_TN` | 3 | Cross-section TN line |
| `PT_PROJET` | 1 | Cross-section projet line |
| `PT_CUT_HATCH` | 1 | Cross-section déblai hatch |
| `PT_FILL_HATCH` | 3 | Cross-section remblai hatch |
| `PT_FRAME` | 7 | Cross-section frame + axes |
| `PT_TEXT` | 7 | Cross-section labels & cotation |
| `PT_AXIS` | 5 | Cross-section axis tick (t = 0) |
| `CARTOUCHE` | 7 | Title block (modelspace + paperspace) |

**Rule:** every entity passes `layer=` in `dxfattribs`. Never draw on layer 0.

---

## 9. PDF rendering contract

Two PDFs, both **fully vector**, rendered directly from `RoadDesign` data via matplotlib — no DXF round-trip. Each PDF starts with a **professional BET-cartouche-style cover page** and carries a **company-name header band** on every subsequent page.

| File | Page | Default H | Default V | Pages |
|---|---|---|---|---|
| `plan_par_sections.pdf` | A1 landscape | auto-fit | auto-fit | 1 cover + ⌈L / sheet_length_pk⌉ |
| `profils_en_travers.pdf` | A4 portrait | 1:100 | 1:25 | 1 cover + N profils |

**Cover page** structure (same for both PDFs, sized per format):
1. **Top band** — company name (28–44 pt, bold) + red accent line + small "ROAD DESIGNER V 1.0" subtitle.
2. **"DOSSIER DE PROJET"** dark pill badge.
3. **Project-title box** — project name (22–36 pt) inside a pink-tinted, red-bordered card; document title in italic below.
4. **INFORMATIONS PROJET box** — bordered, with a red header band: Maître d'ouvrage / BET / Concepteur / Catégorie REFT / Longueur du tracé / Échelle plan PDF / Échelle PT PDF. Subtle row dividers.
5. **CUBATURES box** — horizontal bar chart for Σ Déblai (red) and Σ Remblai (green), Bilan callout with verdict ("Excédent → évacuer" / "Déficit → emprunter").
6. **4-cell footer strip** — N° de plan, Indice, Date, Pages — each with a thin red accent bar on top.
7. **Footer line** + small generation note.

**Page header** structure (on every non-cover page):
- Left: company name (bold).
- Centre: project name + indice (italic).
- Right: page title + page n/N + date.
- Bottom of header: thin red separator.

**Rules:**
- Always use Matplotlib's `Agg` backend (Streamlit Cloud has no GUI).
- Always provide in-memory variants (`to_plan_pdf_bytes`, `to_pt_pdf_bytes`) for the Streamlit downloader.
- Auto-cap PT drawing to the A4 body and label the footer when scales were adjusted.

---

## 10. Streamlit Cloud non-negotiables

1. **No writes to the repo root** or inside the package. Everything goes through `tempfile.TemporaryDirectory()` or stays in `io.BytesIO`.
2. **No `os.getcwd()`-relative paths.** Sample assets resolved through `road_designer.samples_api.sample_*_path()`.
3. **`matplotlib.use("Agg")`** at the top of `pdf_direct.py`.
4. **`requirements.txt` pinned** (Python 3.12 target).
5. **Secret-free**. No API tokens, no Mapbox, no cloud storage. The cartouche fields are typed by the user every session.
6. **Upload size ≤ 20 MB** — set in `.streamlit/config.toml`.
7. **`company_name` is mandatory**. The Generate button stays disabled until it is filled.

---

## 11. Conventions for future sessions

- **Units:** metres and degrees. Grades are stored as fractions (`0.06 = 6 %`) and only converted to % at the UI / DXF boundary.
- **Coordinates:** the project CRS (Lambert-Maroc or local) is preserved exactly from input files — no reprojection. The plan-view rotation to start→end is **drawing only** and never propagates to PK, elevation, or cubature math.
- **PK is always the independent variable.** Profile, table, cubature, Bruckner, and table-column X are all functions of PK. The rotated X is for the plan view only.
- **French labels stay French.** Don't translate `Cotes TN`, `Pentes et Rampes`, `Remb`, `Déb`, `Cubatures`. Translate Python code and comments freely.
- **REFT minima** are visible as named constants on `DesignConfig`, traceable to the REFT category presets.
- **No global mutable state.** Pipeline is one-shot: `DesignConfig + paths → DXF / XLSX / PDF bytes`.
- **Output** outside Streamlit goes to `output/` (gitignored), never to the repo root.
- **Run order**: cross-sections must be computed before cubatures so polygon areas are available to the cubature calculation (Step 7b). `build_design` enforces this.
- **Licence**: the repo is published under the **Beamstack Community License 1.0** (`LICENSE`, `LicenseRef-BCL-1.0`) — a modified MPL 2.0 with a no-sale condition (§3.6) and a "Powered by Beamstack" attribution condition (§3.7). New source files carry the SPDX header `SPDX-License-Identifier: LicenseRef-BCL-1.0` + `SPDX-FileCopyrightText: 2026 Beamstack <https://beam-stack.com>`. Keep `LICENSE`, `NOTICE`, `THIRD-PARTY-NOTICES.md` intact and shipped with every surface. Any user-facing surface (Streamlit app, React SPA) must render a "Powered by Beamstack" credit linked to `https://beam-stack.com`; the FastAPI backend is UI-less and exempt from the badge. Adding a dependency under a copyleft or source-available licence needs a check against `LICENSE` §3 and an entry in `THIRD-PARTY-NOTICES.md`. Contributor terms + the commercial-relicensing grant are in `CONTRIBUTING.md`. See `LICENSING.md` for the plain-language version.

---

## 12. Bug history (C1–C8 + Issues)

| Code | Description | Closed |
|---|---|---|
| C1 | Profile/table X = rotated X instead of PK | Step 2 |
| C2 | `cote_proj` mismatch table-vs-drawing | Step 2 |
| C3 | `from config import *`, hard-coded paths | Step 1 |
| C4 | `smothing_factor` typo + misnomer | Step 1 |
| C5 | Duplicate `*_1.py` files | Step 0 |
| C6 | Missing `min_straight_tangent` constraint | Step 1 |
| C7 | Repo hygiene (stray DXFs, no .gitignore) | Step 0 |
| C8 | Profile lived in PK coordinates (0..L) while plan lived in rotated Lambert (~10⁵), pushing the profile away. **Fix**: `pk_axis_x = vert_x_rot[0] + (pk − pk₀) × h_scale`; `profile_base_y = max(vert_y_rot) + profile_gap_d`. | post-Step 11 |
| Issue 1 | Plan ↔ profile rappels appeared slanted (plan width ≠ road length by design). **Fix**: drop those rappels, replace with **perfectly-vertical** guides linking each profile vertex DOWN to the top of the table — they share the same X (`pk_axis_x`) by construction. | post-launch |
| Issue 3 | PDF text invisibly small + some labels dropped by `ezdxf.addons.drawing`. **Fix**: bypass the DXF round-trip entirely. New `pdf_direct.py` renders every page from `RoadDesign` data with matplotlib primitives; vector output, infinite zoom, full label fidelity. | post-launch |

---

## 13. Roadmap status

| Step | Scope | Done? |
|---|---|---|
| 0 | Repo cleanup: delete `*_1.py`, `.gitignore`, `output/`, git init | ✅ |
| 1 | Config refactor → `DesignConfig` + REFT presets; `min_straight_tangent`; rename `smothing_factor`; `build_design(cfg, axe, terrain, outdir)` | ✅ |
| 2 | Profile/table X axis = PK; `cote_proj` via `v_align.get_z(pk)` | ✅ |
| 3 | Cubatures (plateforme approx) + 7th table row | ✅ |
| 4 | Excel / CSV export | ✅ |
| 5 | Diagramme de Bruckner under the table | ✅ |
| 6 | `samples/` + `synth_terrain.py` + `docs/INPUT_FORMAT.md` | ✅ |
| 7 | Profils en travers (paperspace `PT_xx`) | ✅ |
| 7b | Replace plateforme area with polygon area from cross-sections | ✅ |
| 8 | Cartouches + multi-A1 paperspace `PLAN_xx` | ✅ |
| 9 | PDF export (direct matplotlib, professional cover, A1 plan + A4 PT, company header) | ✅ |
| 10 | Streamlit Cloud UI | ✅ |
| 11 | pytest suite (39 tests) | ✅ |
| post | Issue 1 (vertical guides profile ↔ table) | ✅ |
| post | Issue 3 (PDF DXF-fidelity via direct matplotlib) | ✅ |
| post | Configurable PDF scales (4 knobs, two per PDF) + professional cover | ✅ |
| post | PT defaults H 1:100 / V 1:25 on A4 with auto-cap to body | ✅ |
| post | Repo restructure into `backend/` + `frontends/{streamlit,react}/`; `build_design(return_design=...)`; FastAPI backend + React SPA (§ 15) | ✅ |

**Open for V 1.x:** clothoïdes, calcul dévers, vérification SSD, import LandXML, multi-tracé pour études comparatives.

---

## 14. Version

**`Road-Designer V 1.0`** — first integrated release.

Predecessor: a flat script that produced a single DXF with plan + profile + 6-row table + curvature diagram. Everything else (cubatures, Bruckner, profils en travers, paperspace layouts, PDFs, Streamlit UI, tests, professional cover, company header) is V 1.0.

---

## 15. Deployment architecture — three surfaces

Road-Designer ships as **three independent deployables that share one engine**
(`road_designer/`). None of them depends on another at runtime — each can be deployed,
redeployed, or taken down without affecting the others:

| Surface | Code | Hosting | URL |
|---|---|---|---|
| Streamlit app | `frontends/streamlit/app.py` | Streamlit Community Cloud (always-on fallback) | TODO(user): fill in after first real deploy |
| React SPA | `frontends/react/` | Cloudflare Pages (static build), custom domain `road-designer.beam-stack.com` | TODO(user): confirm after first real deploy |
| FastAPI service | `backend/` | **Google Cloud Run** (container, scale-to-zero, free tier). HF Spaces (Docker) is the documented alternative — **PRO only** since HF's 2025 pricing change. | TODO(user): fill in after first real deploy |

```
                     ┌─────────────────────────┐
                     │   road_designer/         │   the engine — one copy, shared
                     │   (unchanged, see §§3-9) │   by import, never duplicated
                     └────────────┬─────────────┘
                                  │
                 ┌────────────────┼────────────────┐
                 │                                 │
                 ▼                                 ▼
   ┌───────────────────────────┐      ┌──────────────────────────────┐
   │ frontends/streamlit/app.py │      │  backend/app/  (FastAPI)      │
   │ Streamlit Community Cloud  │      │  Google Cloud Run (Docker)    │
   │ — unchanged product,       │      │  POST /designs, GET .../{id}, │
   │   own URL, own users       │      │  GET .../files/{kind},        │
   └───────────────────────────┘      │  GET .../preview, GET /health │
                                       └──────────────┬────────────────┘
                                                       │ fetch (CORS)
                                                       ▼
                                       ┌──────────────────────────────┐
                                       │  frontends/react/ (Vite SPA)  │
                                       │  Cloudflare Pages (static)     │
                                       └──────────────────────────────┘
```

**Why two frontends for one engine:** the Streamlit app is the existing, working product —
it keeps its URL and its users untouched. The React + FastAPI pair is a second, more
"professional-looking" product (custom UI, SVG previews, async job polling) built for
a different deployment story (static SPA + serverless-ish API) without touching the first.

### The one engine change

`road_designer/road_design.py`'s `build_design()` gained a single additive kwarg:
`return_design: bool = False`. When `True`, the returned dict also carries `"design"` — the
constructed `RoadDesign` instance — so `backend/app/routers/preview.py` can read plan/profile/
Bruckner data via the engine's existing public getters (`get_plan_axis`, `get_profile_data`,
etc.) without re-deriving them or adding new engine computation. Default behavior and the
existing positional/keyword order for the CLI and Streamlit callers is unchanged. This is the
**only** change under `road_designer/` — every other constraint in this file (no module-level
constants, `DesignConfig` as the sole configuration contract, French on-drawing labels, PK as
the independent variable, etc.) still applies untouched to any future engine work.

### backend/ — FastAPI service

- **No persistence beyond the process.** `backend/app/jobs.py` is an in-memory dict keyed by
  job id, run through a `ThreadPoolExecutor` (no Celery/Redis/external broker — a small
  free-tier container has no room for one). A background sweep evicts jobs after a 30-minute
  TTL. This means **a restart or redeploy drops all in-flight and completed jobs** — acceptable
  for a synchronous design-generation tool where the client is expected to download its files
  promptly, but worth remembering if this ever needs to survive restarts.
- **Background-thread CPU.** `build_design()` runs in a worker thread *after* the `202` is sent.
  On Cloud Run this requires deploying with `--no-cpu-throttling` (CPU always allocated) or the
  job stalls once the response returns; HF Spaces and most other hosts allocate CPU for the
  instance lifetime by default.
- **Request lifecycle:** `POST /designs` (multipart: axe file + either a terrain CSV or
  synth-terrain params + the `DesignConfigIn`/`CartoucheInfoIn` JSON) returns `202` + a job id
  immediately; the actual `build_design()` call runs in a worker thread. `GET /designs/{id}`
  reports `queued|running|done|error` plus warnings once done. `GET /designs/{id}/files/{kind}`
  streams one of `dxf|xlsx|pdf_plan|pdf_pt`. `GET /designs/{id}/preview` returns the JSON the
  React SVG charts consume (built via `return_design=True`).
- **CORS** is controlled by the `ALLOWED_ORIGIN` env var (defaults to `"*"` — fine for local dev,
  **must** be tightened to the real Cloudflare Pages origin before/at first production deploy).
- **Company-name validation is not a new rule** — `CartoucheInfoIn.company_name` in
  `backend/app/schemas.py` mirrors the same non-empty check `build_design()` already enforces; it
  just surfaces earlier, as an HTTP 422, instead of a 500 from inside the engine.
- **Docker image**: the **repo-root `Dockerfile`** (moved there from `backend/Dockerfile` so
  `gcloud run deploy --source .` finds it) builds from the **repo root** as build context — it
  `COPY`s `road_designer/`, `samples/`, `backend/`, and the Notice Files (`LICENSE`, `NOTICE`,
  `THIRD-PARTY-NOTICES.md`, required by the licence). Runs as non-root `appuser`, sets
  `MPLCONFIGDIR=/tmp/matplotlib` (matplotlib needs a writable config dir). Listens on
  `${PORT:-7860}`: Cloud Run injects `PORT` (8080) automatically, HF Spaces set none so it falls
  back to 7860 (their convention) — the same image runs on both unchanged. `.dockerignore` +
  `.gcloudignore` at the repo root keep the build context small (exclude `frontends/`, venvs,
  `node_modules/`, outputs). Verified end-to-end with `docker build -t road-designer-api .` +
  `docker run -p 18000:7860 ...`: `/health`, a real `POST /designs` against `samples/`, polling
  to `done`, all 4 `/files/{kind}` downloads, and `/preview` all returned correctly from inside
  the built image.
- **`backend/__init__.py` is required**, not boilerplate: without it, pytest resolves
  `backend/tests/` as the top-level `tests` package (since `backend/` itself has no
  `__init__.py` to stop pytest's package-root walk), which collides with the repo-root
  `tests/` package that `backend/tests/conftest.py` imports fixtures from — a circular-import
  `ImportError` at collection time. Keep this file even though it's empty.
- **`backend/tests/` is verified green** (`pytest backend/tests/ -q` inside the built Docker
  image, with the repo-root `tests/` mounted in for its shared fixtures — see § "Local dev
  quick reference" below for the mount syntax on Windows/Docker Desktop): 7 passed. This run
  caught and fixed a real bug: `routers/designs.py`'s 422 handler forwarded pydantic's raw
  `ValidationError.errors()` list straight into `HTTPException(detail=...)`; for the
  `company_name` field validator (a `ValueError`-raising `@field_validator`), pydantic v2
  embeds the *original exception object* under each error's `ctx["error"]`, which
  `JSONResponse`'s plain `json.dumps` can't serialize — the missing-`company_name` request
  crashed with a 500 instead of returning the intended 422. Fixed by projecting each error down
  to its plain-data fields (`type`/`loc`/`msg`) before raising. Watch for this same pattern
  (`exc.errors()` forwarded verbatim) in any future custom validator added to `schemas.py`.
- **Keep-alive**: `.github/workflows/keep-alive-backend.yml` cron-pings the backend every ~12
  minutes via the `BACKEND_HEALTH_URL` repo secret. It is for hosts where an idle instance is
  free (HF PRO, Render, Koyeb). **Do not point it at the Cloud Run deployment** — with
  `--no-cpu-throttling` a kept-warm instance is billed continuously and blows the free monthly
  allotment. No-ops gracefully if the secret is unset.

### frontends/react/ — Vite + React + TypeScript + Tailwind

- Hand-written UI primitives in a shadcn-like style (Button, Field, Select, Card, Section) —
  no shadcn CLI run, so the app has zero extra network dependency at build time. `npx shadcn@latest
  add <component>` can swap any of these in later if desired; see `frontends/react/README.md`.
- `src/lib/api.ts` is the only place that knows the backend's URL — it reads
  `VITE_API_BASE_URL`, a **Vite build-time** env var (baked into the JS bundle at `npm run build`,
  not read at runtime). On Cloudflare Pages this must be set in the dashboard under
  **Settings → Environment variables** (Production and Preview), not in `wrangler.toml`.
- `src/hooks/useDesignJob.ts` polls `GET /designs/{id}` every 2 s until `done`/`error` — mirrors
  the backend's own job-lifecycle contract, no websockets.
- The plan/profile/Bruckner charts (`src/components/chart/InteractiveLineChart.tsx`) are a
  from-scratch SVG component (wheel-zoom, drag-pan, nearest-point hover) — no charting library
  dependency, kept deliberately small for a static-hosting bundle-size budget.
- Deploys as a static build (`npm run build` → `dist/`) to Cloudflare Pages; `wrangler.toml` exists
  for CLI-based deploys as an alternative to the dashboard's Git-integration path.

### Local dev quick reference

```bash
# FastAPI backend (repo root)
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --reload
# → http://localhost:8000, CORS defaults to "*" for local dev

# React frontend (frontends/react/)
cp .env.example .env.local        # VITE_API_BASE_URL=http://localhost:8000
npm install
npm run dev

# Streamlit app (unchanged) — from repo root
streamlit run frontends/streamlit/app.py

# backend/tests/ inside the built Docker image, without installing anything on the host
# (the image already has every pinned dependency; mount the repo-root tests/ dir in for
# backend/tests/conftest.py's shared axe_path/terrain_path fixtures). On Windows + Docker
# Desktop, the //c/... double-slash form avoids Git-Bash path mangling of -v:
docker build -t road-designer-api .
docker run --rm -v "//c/path/to/Road_designe/tests:/app/tests:ro" \
    --entrypoint pytest road-designer-api backend/tests/ -q
```

### Env vars / secrets to fill in after first real deploy

| Where | Name | Set to |
|---|---|---|
| Cloud Run service (`gcloud run ... --set-env-vars`) / HF Space Variables | `ALLOWED_ORIGIN` | The SPA's origin — the custom domain `https://road-designer.beam-stack.com` (comma-add `https://road-designer.pages.dev` to keep the fallback) |
| Cloudflare Pages dashboard | `VITE_API_BASE_URL` | The deployed backend URL (Cloud Run `https://…run.app`, or an HF Space `https://<user>-<space>.hf.space`) |
| GitHub repo secret (optional) | `BACKEND_HEALTH_URL` | `https://<backend-host>/health` — only for HF/Render/Koyeb, **not** Cloud Run with `--no-cpu-throttling` |
| Streamlit Cloud dashboard | "Main file path" setting | `frontends/streamlit/app.py` (must be updated manually post-move — cannot be set from the repo) |

**[`DEPLOYMENT.md`](DEPLOYMENT.md)** (repo root) is the full step-by-step, beginner-oriented
walkthrough — backend to **Google Cloud Run** (Part A, `gcloud run deploy --source .` from the
repo root, `--no-cpu-throttling` for the background-thread jobs), React SPA to Cloudflare Pages
(Part B), Streamlit path fix (Part D), and **Part G** for moving the backend to Hugging Face
Spaces later (needs PRO since HF's 2025 pricing change; the `Dockerfile` is host-neutral so the
image itself is unchanged). It also covers the licence obligations that touch deployment
(Notice Files in the image, "Powered by Beamstack" on the two UIs) and the Cloud-Run-vs-HF-PRO
cost crossover. Point the user there for the actual deploy; keep this section as the technical
reference for what each piece does.
