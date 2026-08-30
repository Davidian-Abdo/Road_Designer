<!-- SPDX-FileCopyrightText: 2026 Beamstack <https://beam-stack.com> -->
<!-- SPDX-License-Identifier: LicenseRef-BCL-1.0 -->

**English**&nbsp;·&nbsp;[Français](README.fr.md)

# Road Designer V 1.0

**Automatic generation of BET-grade civil-engineering road-design deliverables** — from a terrain model (MNT) and a horizontal alignment file to a DXF, an earthwork Excel workbook, and two print-ready PDFs (A1 sectioned plan + longitudinal profile, A3 cross-sections).

Built for civil-engineering consultancies (bureaux d'études techniques) working to Moroccan REFT standards (categories 1 / 2 / 3) or equivalents such as ARP / ICTAAL. All on-screen and on-drawing labels are in French, by design — these are the deliverables a Maghreb BET actually issues.

```
terrain.csv  ─┐
              │   ┌──────────────────────────┐    ┌─ road_design.dxf
axe.txt    ───┼─► │  Road Designer V 1.0    ├─►  ├─ tableau.xlsx
              │   │  (SLSQP optimisation    │    ├─ plan_par_sections.pdf
DesignConfig ─┘   │   + earthworks + PDF)   │    └─ profils_en_travers.pdf
                  └──────────────────────────┘
```

---

## At a glance

| Capability | Detail |
|---|---|
| **Plan view** (tracé en plan) | Straight segments + circular arcs, read from a standard BET axe file (`D` / `C` blocks with `XC YC R`) |
| **Vertical alignment** (ligne rouge) | Optimised by SLSQP — minimises ∑\|Z_project − Z_ground\| under REFT constraints (max grade, min crest/sag radius, min straight-tangent length between two vertical curves) |
| **Vertical curves** | Symmetric parabolas, K-value chosen per PVI (largest feasible radius, capped by the REFT minimum) |
| **Earthworks** (cubatures) | Average-end-area method using the real polygons from the cross-sections; cut and fill split at every `h = 0` transition |
| **Mass-haul diagram** (Bruckner) | `M(PK) = Σ (V_fill − V_cut)`, annotated at the extrema (the natural haul boundaries) |
| **Cross-sections** (profils en travers) | Configurable typical section (carriageway + shoulders + ditches + side slopes) with per-category H/V slope ratios |
| **PDF deliverables** | Plan + longitudinal profile sliced into `sheet_length_pk` windows (A1 landscape); one cross-section per page (A3 portrait by default) |
| **Professional cover** | Company header, "DOSSIER DE PROJET" badge, project title, information / earthworks blocks (with horizontal bars) / index / date / drawing number |
| **Page header** | Top band with company name (left), project centred, page number + date on the right — on every non-cover page |
| **Standards** | `REFT_CAT_1` / `CAT_2` / `CAT_3` presets, or custom parameters via the UI |

---

## Quick start

### 1. Install

```bash
git clone https://github.com/<your-org>/road-designer.git
cd road-designer
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Run the Streamlit UI (recommended)

```bash
streamlit run frontends/streamlit/app.py
```

Then open `http://localhost:8501`. Load the bundled example or your own files, adjust the parameters in the sidebar, click **Générer**, and download the DXF + XLSX + 2 PDFs.

### 2b. React UI + FastAPI API (alternative)

A second, more "product"-style frontend (full form, interactive SVG previews, async job polling) lives in `frontends/react/` and talks to a FastAPI service in `backend/` — a separate product from the Streamlit app above, sharing the same `road_designer/` engine. See `backend/README.md` and `frontends/react/README.md` for local dev, [`DEPLOYMENT.md`](DEPLOYMENT.md) for the step-by-step deploy guide (Google Cloud Run + Cloudflare Pages + Streamlit Cloud update; Hugging Face Spaces documented as an alternative backend host), and `CLAUDE.md` § 15 for the full architecture.

```bash
# terminal 1 — API
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --reload

# terminal 2 — SPA
cd frontends/react && npm install && npm run dev
```

### 3. Command-line mode

```bash
python main.py \
    --axe samples/sample_axe.txt \
    --terrain samples/sample_terrain.csv \
    --out output \
    --category CAT_1 \
    --company "BET Atlas Ingénierie" \
    --projet "Liaison RR501 — Section 3" \
    --designer "M. Benali"
```

Output files land in `output/`.

---

## Input formats

### `axe.txt` — horizontal alignment

Classic Moroccan BET format:

```
        1512.101   447289.137   254023.033        ← PK0  X0  Y0
 D1     GIS = 254.706g     38.350                 ← straight segment, L = 38.35 m
        1550.451   447260.090   253997.992        ← end station of D1

 C1     XC = 447276.414                           ← curve: centre X
        YC = 253979.057                           ← centre Y
        R  =  25.000        19.856               ← signed radius, L = 19.856 m
        1570.308   447251.467   253980.683        ← end station of C1
 …
```

The **sign of the radius** gives the turn direction: positive = left turn (trigonometric), negative = right turn. See `docs/INPUT_FORMAT.md` for the full grammar and an annotated example.

### `terrain.csv` — digital terrain model (MNT)

```
X,Y,Z
447289.137,254023.033,778.853
447286.454,254020.720,778.598
…
```

Three comma-separated columns. The coordinate system (Lambert-Maroc, UTM, or local) must match the axe file. The engine builds a Delaunay TIN and falls back to nearest-neighbour outside the convex hull.

Recommended density: 1–5 m for a detailed preliminary design, 5–10 m for an outline design.

### Generate a synthetic test MNT

```bash
python -m samples.synth_terrain \
    --axe samples/sample_axe.txt \
    --out samples/sample_terrain.csv \
    --z-base 780 --slope 0.02 --amplitude 4 --wavelength 600
```

For trying the tool without a real MNT.

---

## Architecture (post-refactor V 1.0)

Three independent deployment surfaces share one `road_designer/` engine: Streamlit Community Cloud, a React SPA on Cloudflare Pages backed by a FastAPI service on Google Cloud Run, and the local CLI. None depends on another at runtime.

```
road_designer/          ← engine — unchanged, shared by all 3 surfaces
├── config.py           ← @dataclass DesignConfig + REFT_CAT_1/2/3
├── mnt_engine.py        ← TerrainModel (TIN + KDTree fallback)
├── axe_parser.py        ← LineSegment, ArcSegment, AlignmentParser
├── geometry_engine.py   ← normal, offset, rotation
├── design_logic.py      ← VerticalAlignment (parabolas)
├── road_design.py       ← RoadDesign orchestrator + build_design()
├── cross_section.py     ← TypicalSection + cut/fill polygons
├── cubature.py          ← average-end-area volumes + Bruckner
├── dxf_export.py        ← full DXF assembly (modelspace + paperspace)
├── excel_export.py      ← 12-column XLSX + REFT-warnings sheet
├── pdf_direct.py        ← vector matplotlib PDF (BET cover + headers)
└── samples_api.py       ← sample-file access + synthetic terrain

samples/                 ← bundled example files
docs/INPUT_FORMAT.md     ← input grammar
tests/                   ← engine pytest suite (41 tests)
main.py                  ← CLI
CLAUDE.md / AGENTS.md    ← reference for maintenance sessions

backend/                 ← FastAPI API (deploys to Google Cloud Run, Docker)
frontends/
├── streamlit/           ← app.py Streamlit (deploys to Streamlit Community Cloud)
└── react/               ← Vite/React/TypeScript SPA (deploys to Cloudflare Pages)
```

See [`CLAUDE.md`](CLAUDE.md) for the detailed pipeline description, the civil-engineering vocabulary, the DXF layer convention, the PDF contract, and § 15 for the three-surface deployment architecture. See also `backend/README.md` and `frontends/react/README.md` for local dev and the React + FastAPI deploy.

---

## Default scales

| PDF | Page | H | V | Vertical exaggeration |
|---|---|---|---|---|
| Plan + longitudinal profile (`plan_par_sections.pdf`) | A1 landscape | auto-fit (~1:700–1:1000) | auto (~1:70–1:100) | ≈ ×10 |
| Cross-sections (`profils_en_travers.pdf`) | A4 portrait | **1:100** | **1:25** | ≈ ×4 |

The four scales (two per PDF) are **editable in the UI** ("Mise en page / PDF" field). Set 0 to return to auto-fit.

The cross-section lateral extent defaults to **1.5 × carriageway width per side** (total = 3 × carriageway width). For a 7 m carriageway → ± 10.5 m → 21 m drawn. Editable via the "Étendue PT ±" field.

**A4 auto-cap** — if the user-forced H/V scales produce a drawing larger than the A4 usable body (200 × 235 mm), the renderer ratchets the affected scales down to fit. The footer then reads "*échelle ajustée pour A4*" and reports the scales actually used. For a 7 m carriageway with h ≈ 4 m of cut/fill, the defaults produce a drawing of about **200 × 235 mm** (95 % × 79 % of the A4 body).

---

## Tests

```bash
pytest tests/ -v            # engine (41 tests)
pytest backend/tests/ -v    # FastAPI API (7 tests) — see backend/README.md for setup
```

The 41 engine tests pin: axe grammar, parabola continuity, crest/sag sign, REFT floor, `h = 0` split in the earthworks, Bruckner identities, 2D geometry, profile/plan registration, PT scale selection, `company_name` validation, and the layout tests (profile below plan, monotone PK, consistent V scale). The 7 `backend/` tests cover the full HTTP job lifecycle (submit → poll → 4 downloads → preview).

---

## Conventions

- **Units**: metres and degrees; grades are stored as fractions (0.06 = 6 %) and shown as % at the boundaries (UI / DXF).
- **PK is the independent variable**: profile, table, Bruckner, and earthworks are all indexed by PK. The plan rotation to the start→end axis is drawing-only and never propagates to the maths.
- **DXF layers**: `AXIS / EDGES / GROUND / PROJECT / TABLE / TABLE_TEXT / TABLE_CUBATURE / HAUTEURS_REM / HAUTEURS_DEB / RAPPEL / BUBBLES / CUTTING_LINES / CURV_DIAG / BRUCKNER / PT_* / CARTOUCHE`. Nothing is drawn on layer 0.
- **Output**: `output/` is gitignored. The Streamlit layer never writes to the repo root — everything goes through `tempfile.TemporaryDirectory` then `st.download_button`.

---

## Licence

**Beamstack Community License 1.0** (`LicenseRef-BCL-1.0`) — a *source-available* licence; **not** an OSI "open source" licence. It is a renamed, modified version of the Mozilla Public License 2.0 (permitted by its Section 10.3), with two added conditions:

- **No Sale** (Section 3.6) — you may not sell the software, charge for access to it, host it as a paid service, or bundle it into a paid product whose value comes mainly from its functionality. Internal use stays free, **including using it to produce paid deliverables for your clients**, as long as it is not the software itself that is being sold.
- **Beamstack attribution** (Section 3.7) — any app, site, or tool built on this code must display "Powered by Beamstack" (or the Beamstack logo), linked to <https://beam-stack.com>, somewhere visible (an About screen, a footer, a splash screen…), credit Beamstack in its documentation, and keep the `LICENSE`, `NOTICE`, and `THIRD-PARTY-NOTICES.md` files intact.

Changes to the project's own files must be published under the same licence (file-level copyleft, inherited from MPL 2.0). Full obligations: [`LICENSE`](LICENSE); plain-language summary: [`LICENSING.md`](LICENSING.md) and [`NOTICE`](NOTICE).

**Commercial licence** — for anything not covered (resale, paid hosting, removing the attribution, a closed fork), a commercial licence or a written waiver is available: **askdaoudi@gmail.com**.

© 2026 **Beamstack**. "Beamstack" is a trademark registered with OMPIC (Morocco). Beamstack is not yet incorporated; the rights holder of record is Abdellah Daoudi (sole proprietor).

## Standards

Reference standards: [REFT — Recueil d'Études Techniques Fondamentales (Morocco)](https://www.equipement.gov.ma/) categories 1, 2, and 3. For France, the parameters roughly correspond to ICTAAL / ICTAVRU; when in doubt, check the minima in your own brief.

This tool is **not certified for signature**: it produces preliminary and intermediate deliverables that the signing engineer must review and validate.

---

## Roadmap V 1.x

- [ ] Clothoids (progressive transitions between straight and circular arc)
- [ ] Superelevation (dévers) computation with a dedicated diagram
- [ ] Sight-distance (SSD) verification
- [ ] LandXML import / GeoJSON export
- [ ] Multi-alignment generation for comparative studies

Suggestions and issues: see the GitHub repository.
