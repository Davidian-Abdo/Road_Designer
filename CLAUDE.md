# Road Designer V 1.0

A Python application that produces BET-grade civil-engineering road-design deliverables (tracé en plan, profil en long, profils en travers, tableau, cubatures, diagramme de Bruckner, cartouches A1) from a terrain database and a horizontal alignment file.

Target user: a road-design civil engineer working in a Bureau d'Études Techniques (BET), Maghreb context, following Moroccan REFT standards (or equivalent ARP/ICTAAL). All on-drawing labels are in French.

Default deployment: Streamlit Community Cloud (web UI) with a local CLI as a secondary path.

---

## 1. What the tool does

```
Inputs                                                    Output (single .dxf)
─────────────────────────────────────────────────────     ─────────────────────────
terrain CSV  (X, Y, Z points)                             • Tracé en plan
axe file     (segments droits D + courbes C: XC,YC,R)     • Profil en long
DesignConfig (REFT category, road width, talus, …)        • Tableau (7 rows)
                                                          • Diagramme des courbures
       │                                                  • Diagramme de Bruckner
       ▼                                                  • Profils en travers (paperspace)
  RoadDesign  ──►  VerticalAlignment  ──►  DXF assembly   • Cartouches A1 multi-sheets
       │                                                  ─────────────────────────
       └──►  TerrainModel (TIN + KDTree fallback)         + tableau.xlsx  (cubatures)
                                                          + report.pdf    (résumé)
```

The vertical alignment (ligne rouge) is **optimised** — not hand-traced. PVIs are placed where the smoothed TN curvature changes by more than `MAX_GRADE_CHANGE`, then SLSQP minimises `Σ |Z_projet − Z_TN|` under three constraints:

1. `|grade| ≤ MAX_PENTE`
2. each vertical curve must fit between adjacent PVIs (`L = R·|Δg|` must be ≤ available tangent)
3. **new in v1.0:** the straight portion between two curves must be ≥ `MIN_STRAIGHT_TANGENT_LENGTH`

Vertical curves are parabolic with per-curve radius (K-value) selection: max feasible radius, capped by `max_radius`, floored by REFT minimum for summit vs. sag.

---

## 2. Vocabulary (read before editing)

| Term | Meaning |
|---|---|
| **PK** | Point Kilométrique — chainage along the axis, in metres. The primary independent variable. |
| **Tracé en plan** | Plan view of the alignment (straights + arcs, sometimes clothoids). |
| **Profil en long** | Longitudinal profile — TN (ground) and projet (designed road) elevation vs PK. |
| **Profil en travers** | Cross-section — perpendicular slice at a given PK showing TN, chaussée, accotements, fossés, talus. |
| **Ligne rouge** | The vertical alignment of the projet (red line on the profile drawing). |
| **PVI** | Point of Vertical Intersection — where two tangent grades meet. Apex of each parabolic vertical curve. |
| **PVC / PVT** | Point of Vertical Curvature / Tangency — start and end of a vertical curve. |
| **K-value** | `K = L / |Δg|` (m per %). Used here interchangeably with curve radius `R` (the code names the constant `R_SUMMIT` / `R_SAG`). |
| **Sommet / Cuvette** | Summit (crest, Δg < 0) / sag (Δg > 0) vertical curve. |
| **Déblai / Remblai** | Cut / fill. Code abbreviates `Déb` / `Remb`. |
| **Cubature** | Earthwork volume (m³) between two consecutive cross-sections. |
| **Diagramme de Bruckner** | Mass-haul diagram: `M(PK) = Σ (V_remblai − V_déblai)` from origin to PK. |
| **Cartouche** | Title block on a paper sheet (project, BET, designer, échelle, n° de plan, indice, date). |
| **Dévers** | Superelevation — transverse slope of the chaussée in curves. |
| **REFT** | Moroccan road design standard catalogue (Recueil d'Études Techniques Fondamentales). |
| **BET** | Bureau d'Études Techniques — engineering consultancy that issues the deliverable. |
| **TN** | Terrain Naturel — existing ground surface. |

---

## 3. Repository layout (target — post-refactor)

```
Road_designe/
├── CLAUDE.md                      ← this file
├── README.md                      ← user-facing intro (Step 9)
├── requirements.txt               ← pinned for Streamlit Cloud
├── .streamlit/
│   └── config.toml                ← theme, maxUploadSize
├── .gitignore                     ← *.dxf, *.xlsx, Road_venv/, __pycache__/, output/
│
├── app.py                         ← Streamlit entry point (Step 9)
│
├── road_designer/                 ← installable package
│   ├── __init__.py
│   ├── config.py                  ← @dataclass DesignConfig + REFT presets
│   ├── mnt_engine.py              ← TerrainModel (TIN + KDTree)
│   ├── axe_parser.py              ← LineSegment, ArcSegment, AlignmentParser
│   ├── geometry_engine.py         ← compute_normal, offset_points, …
│   ├── design_logic.py            ← VerticalAlignment (parabolic curves)
│   ├── road_design.py             ← RoadDesign orchestrator
│   ├── cubature.py                ← areas + volumes + Bruckner       (Steps 3, 5)
│   ├── cross_section.py           ← TypicalSection, CrossSectionDrawer (Step 7)
│   ├── dxf_export.py              ← all ezdxf assembly (model + paperspace)
│   ├── excel_export.py            ← XLSX/CSV writers                  (Step 4)
│   ├── pdf_report.py              ← summary PDF                       (later)
│   └── preview.py                 ← matplotlib previews for Streamlit (Step 9)
│
├── samples/                       ← read-only, shipped with the app
│   ├── sample_axe.txt
│   ├── sample_terrain.csv
│   └── synth_terrain.py           ← generate a synthetic CSV from any axe (Step 6)
│
├── docs/
│   └── INPUT_FORMAT.md            ← axe + CSV grammar with annotated example (Step 6)
│
├── tests/                         ← pytest suite                      (Step 10)
│   ├── test_axe_parser.py
│   ├── test_vertical_alignment.py
│   ├── test_cubature.py
│   └── test_geometry.py
│
└── output/                        ← gitignored, local CLI dumps here
```

Until Step 1 the layout is still the flat repo we started from. Steps 0 and 1 do the flattening + packaging.

---

## 4. The data flow in one picture

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
                                       │ 2. rotate plan to start-end     │
                                       │ 3. dense sampling of axis       │
                                       │ 4. TN at every dense PK          │
                                       │ 5. generate_optimized_pvis()    │
                                       │       └─SLSQP w/ constraints    │
                                       │ 6. VerticalAlignment(pvis,…)    │
                                       │ 7. Z_projet at every PK         │
                                       │ 8. compute_cubatures()          │  (Step 3)
                                       │ 9. compute_bruckner()           │  (Step 5)
                                       └─────────────┬───────────────────┘
                                                     │
                  ┌──────────────────────────────────┼──────────────────────────────┐
                  ▼                                  ▼                              ▼
         ┌────────────────┐                ┌────────────────┐              ┌────────────────┐
         │  dxf_export    │                │  excel_export  │              │  pdf_report    │
         │ • plan         │                │ • table 7 rows │              │ • cover        │
         │ • profile      │                │ • cubatures    │              │ • totals       │
         │ • table        │                │ • Bruckner     │              │ • flags        │
         │ • Bruckner     │                └────────────────┘              └────────────────┘
         │ • cross-sects  │
         │ • cartouches   │
         └────────────────┘
```

---

## 5. The config dataclass (target shape — Step 1)

```python
# road_designer/config.py
from dataclasses import dataclass, field

@dataclass
class TypicalSection:
    chaussee_width:   float = 7.0     # m
    crown_slope:      float = 0.025   # 2.5 %
    accotement_width: float = 1.5     # m each side
    accotement_slope: float = 0.04
    ditch_depth:      float = 0.5
    ditch_width:      float = 1.0
    talus_deblai_h_v: float = 2/3     # H/V — déblai
    talus_remblai_h_v:float = 3/2     # H/V — remblai

@dataclass
class CartoucheInfo:
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
    design_speed:           float = 90.0     # km/h
    road_category:          str   = "CAT_1"  # CAT_1 | CAT_2 | CAT_3

    # Horizontal
    road_width:             float = 7.0
    profile_sampling:       float = 1.0

    # Vertical (REFT minima for the active category)
    r_summit:               float = 1500.0
    r_sag:                  float = 1000.0
    max_radius:             float = 6000.0
    max_pente:              float = 6.0       # %
    min_tangent_length:     float = 120.0     # between PVIs
    min_straight_tangent:   float = 50.0      # between curve ends (new in v1.0)
    max_grade_change:       float = 0.005
    vertical_band_ratio:    float = 0.13      # was the mis-named "smothing_factor"

    # Drawing scales
    h_scale:                float = 1.0
    v_scale:                float = 10.0
    profile_gap_d:          float = 100.0

    # Cubature / cross-section
    typical_section:        TypicalSection = field(default_factory=TypicalSection)
    cross_section_step_pk:  int   = 1        # every Nth profile
    cross_section_extent:   float = 25.0
    cross_section_scale_h:  float = 100.0
    cross_section_scale_v:  float = 100.0

    # Layout / paper
    sheet_length_pk:        float = 500.0
    sheet_format:           str   = "A1"
    cartouche:              CartoucheInfo = field(default_factory=CartoucheInfo)

    # Output filenames (Step 9 adds the two PDFs)
    dxf_filename:           str   = "road_design.dxf"
    xlsx_filename:          str   = "tableau_profil_en_long.xlsx"
    pdf_plan_filename:      str   = "plan_par_sections.pdf"   # one page per
                                                              # sheet_length_pk
    pdf_pt_filename:        str   = "profils_en_travers.pdf"  # one page per PT
    pdf_dpi:                int   = 200                       # render quality


REFT_CAT_1 = DesignConfig()                               # 80–100 km/h (default)
REFT_CAT_2 = DesignConfig(design_speed=70, road_category="CAT_2",
                          r_summit=1500, r_sag=1000, max_pente=7.0)
REFT_CAT_3 = DesignConfig(design_speed=50, road_category="CAT_3",
                          r_summit=750,  r_sag=500,  max_pente=8.0)
```

**Rule for future edits:** any new design constant goes here. **Never** introduce module-level `CONSTANTS = …` in business modules; accept a `DesignConfig` instance instead.

---

## 6. DXF layer convention

| Layer | Color | Used for |
|---|---|---|
| `AXIS` | 5 (blue) | Centreline polyline |
| `EDGES` | 8 (grey) | Road edges in plan |
| `GROUND` | 3 (green) | TN polyline on profile |
| `PROJECT` | 1 (red) | Projet (ligne rouge) polyline on profile |
| `RAPPEL` | 2 (yellow, DASHED) | Vertical leaders plan ↔ profile |
| `HAUTEURS` | 1 / 3 | `Remb` / `Déb` height labels |
| `TABLE` | 7 (white/black) | Table frame lines |
| `TABLE_TEXT` | 7 | Table cell text |
| `BUBBLES` | 4 (cyan) | Profile number bubbles |
| `CUTTING_LINES` | 6 (magenta) | Cross-section indicators on plan |
| `TICKS` | 6 | Arc endpoint ticks |
| `ARC_ARROW` | 4 | Curved arrow + `R=… L=…` label |
| `STRAIGHT_ARROW` | 4 | Straight segment length arrow |
| `BRUCKNER` | 6 | Mass-haul curve (Step 5) |
| `PT_*` | per element | Profil en travers entities (Step 7) |
| `CARTOUCHE` | 7 | Title block (Step 8) |

**Rule:** every entity passes `layer=` in `dxfattribs`. Never draw on layer 0.

---

## 7. Roadmap — single source of truth

| Step | Scope | Touches | Done? |
|---|---|---|---|
| 0 | Repo cleanup: delete `*_1.py`, `.gitignore`, `output/`, git init | repo root | ✅ |
| 1 | Config refactor → `DesignConfig` dataclass + REFT presets; add `min_straight_tangent`; rename `smothing_factor`; refactor `main.py` into `build_design(cfg, axe, terrain, outdir)` | `road_designer/config.py`, `road_design.py`, `main.py` | ✅ |
| 2 | Profile/table X axis = PK (not rotated X); table `cote_proj` via `v_align.get_z(pk)` | `road_design.py` | ✅ |
| 3 | Cubatures (plateforme approx) + 7th table row | `cubature.py`, `dxf_export.py` | ✅ |
| 4 | Excel / CSV export | `excel_export.py` | ✅ |
| 5 | Diagramme de Bruckner under the table | `cubature.py`, `dxf_export.py` | ✅ |
| 6 | `samples/` (axe + terrain) + `synth_terrain.py` + `docs/INPUT_FORMAT.md` | `samples/`, `docs/` | ✅ |
| 7 | Profils en travers (paperspace `PT_01..M`) | `cross_section.py`, `dxf_export.py` | ✅ |
| 7b | Replace plateforme `A(pk)` with polygon `A(pk)` from cross-sections | `cubature.py` | ✅ |
| 8 | Cartouches + multi-A1 paperspace `PLAN_01..N` | `dxf_export.py` | ✅ |
| **9** | **PDF export — two files: (a) `plan_par_sections.pdf`, one A1 page per `sheet_length_pk` window (re-using `PLAN_01..N` layouts from Step 8); (b) `profils_en_travers.pdf`, one A4 page per PT (re-using `PT_01..M` layouts from Step 7). Rendered via `ezdxf.addons.drawing` matplotlib backend.** | **`pdf_export.py`** | **✅** |
| 10 | Streamlit Cloud UI (`app.py`, `.streamlit/`, `requirements.txt`) | repo root | ✅ |
| 11 | pytest suite | `tests/` | ✅ |

Each step lands on a clean, runnable repo. After Step 9 the user opens the Streamlit URL, uploads (or picks samples), tunes config, and downloads DXF + XLSX in one click.

---

## 8. Bugs being fixed (cross-referenced)

| Code | Description | Closed in Step |
|---|---|---|
| C1 | Profile/table X = rotated X instead of PK | 2 |
| C2 | `cote_proj` mismatch table-vs-drawing | 2 |
| C3 | `from config import *`, hard-coded paths | 1 |
| C4 | `smothing_factor` typo + misnomer | 1 |
| C5 | Duplicate `*_1.py` files | 0 |
| C6 | Missing `min_straight_tangent` | 1 |
| C7 | Repo hygiene (27 stray DXFs, no .gitignore) | 0 |

---

## 9. Streamlit Cloud non-negotiables

When editing for Step 9 (and anything that touches I/O before then):

1. **No writes to the repo root or any path inside the package.** Everything goes through `tempfile.TemporaryDirectory()` or stays in `io.BytesIO`.
2. **No `os.getcwd()`-relative paths.** Resolve sample assets through `importlib.resources.files("samples") / "sample_axe.txt"`.
3. **`matplotlib.use("Agg")`** at the top of `preview.py` — Streamlit Cloud has no GUI backend.
4. **`requirements.txt` pinned**. No `latest`, no `>=`.
5. **Secret-free**. No API tokens, no Mapbox, no cloud storage. The cartouche fields are typed by the user every session (or restored from a JSON the user uploads).
6. **Upload size ≤ 20 MB** for both files; surfaced in `.streamlit/config.toml`.

---

## 10. Conventions for future Claude sessions

- **Units:** metres and degrees. Grades are stored as fractions (0.05 = 5 %) internally; only displayed as % at the UI/drawing boundary.
- **Coordinates:** the project CRS (Lambert-Maroc or local) is preserved exactly as in the input files — no reprojection. The rotation to align the plan view to the start-end vector is **drawing only** and never propagates to PK, elevation, or cubature math.
- **Independent variable is always PK.** Cross-section, cubature, Bruckner, and table columns are functions of PK. The rotated X coordinate is for the plan view only.
- **French labels stay French.** Don't translate `Cotes TN`, `Pentes et Rampes`, `Remb`, `Déb`, `Cubatures`. Translate code/comments freely.
- **Standards reference:** REFT (Maroc) for minima. Keep `R_MIN_SOMMET_*` and `R_MIN_CUVETTE_*` as named constants visible from `config.py` so a reviewer can trace each value to its source.
- **Never** introduce a global mutable state. The pipeline is one-shot: `DesignConfig + paths → DXF/XLSX bytes`.
- **Output files** outside Streamlit go to `output/` (gitignored), never to the repo root.

---

## 11. PDF export contract (Step 9)

Two PDFs are produced from the **same** DXF the user gets — never re-implement
geometry. The renderer is `ezdxf.addons.drawing` with the matplotlib backend
and `matplotlib.backends.backend_pdf.PdfPages`.

| File | One page per | Driven by | Page size |
|---|---|---|---|
| `plan_par_sections.pdf` | A1 layout `PLAN_xx` | `cfg.sheet_length_pk` (Step 8) | A1 landscape |
| `profils_en_travers.pdf` | A4 layout `PT_xx` (one PT per layout) | `cfg.cross_section_step_pk` (Step 7) | A4 portrait |

Rules
- **No new geometry in `pdf_export.py`.** It opens the existing DXF, walks
  the layouts in name order, and rasterises each to a PDF page.
- **Resolution** is `cfg.pdf_dpi` (default 200). Vector mode is preferred when
  the backend supports it (matplotlib does — text stays selectable).
- **In-memory variants** (`to_plan_pdf_bytes`, `to_pt_pdf_bytes`) are mandatory
  for the Streamlit downloader (rule 9.1).
- **Page order is deterministic**: `sorted(name for name in doc.layouts
  if name.startswith(prefix))`.
- **First page** of each PDF prepends a one-page cover with the cartouche
  fields (`projet`, `BET`, `designer`, `indice`, `date`, total length, total
  cubatures) so the printed document is self-describing.

---

## 12. Version

`Road Designer V 1.0` — first integrated release. Predecessor: a flat script that produced a single DXF with plan + profile + 6-row table + curvature diagram.
