"""Road Designer V 1.0 — Streamlit Community Cloud UI.

Entry point that any user of the deployed app sees. Three principles:

  1. **No writes outside tempfile**. Outputs are streamed via st.download_button.
  2. **No hard-coded paths**. Samples are resolved via samples_api.
  3. **Every DesignConfig knob exposed**. Sidebar drives the dataclass.

Run locally with:  ``streamlit run frontends/streamlit/app.py`` (from the repo
root) or ``streamlit run app.py`` (from this directory).

This file lives under ``frontends/streamlit/`` alongside the React+FastAPI
frontend under ``frontends/react/`` — both are separate products sharing the
same ``road_designer`` engine (see CLAUDE.md § "Three-surface architecture").
Nothing below changed when this file moved except the two path fixups
immediately below (repo-root import path, docs/ lookup).
"""
from __future__ import annotations

import io
import sys
import tempfile
from dataclasses import replace
from pathlib import Path

# This file lives at <repo_root>/frontends/streamlit/app.py. Streamlit adds
# this file's own directory to sys.path, not the repo root, so ``road_designer``
# would not be importable without this. Mirrors tests/conftest.py's fixup.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import streamlit as st

from road_designer.config import (
    BeamStackContact,
    CartoucheInfo,
    DesignConfig,
    TypicalSection,
    get_preset,
)
from road_designer.road_design import build_design
from road_designer.samples_api import (
    generate_synthetic_terrain,
    sample_axe_bytes,
    sample_axe_path,
    sample_terrain_bytes,
    sample_terrain_path,
)


# ─────────────────────────────────────────────────────────────────────────────
# Page setup
# ─────────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Road Designer V 1.0",
    page_icon="🛣️",
    layout="wide",
)

st.markdown(
    """
    <style>
      .beamstack-header {
        display: flex;
        align-items: center;
        gap: 1.1rem;
        padding: 0.9rem 0 1.0rem 0;
        margin-bottom: 0.3rem;
        border-bottom: 1px solid rgba(49, 64, 86, 0.18);
      }
      .beamstack-name {
        font-size: clamp(1.8rem, 3.2vw, 4rem);
        line-height: 0.95;
        font-weight: 800;
        letter-spacing: 0;
        color: #18212f;
      }
      .beamstack-divider {
        width: 3px;
        height: clamp(2.2rem, 4vw, 3.0rem);
        background: #d92727;
        border-radius: 2px;
        flex: 0 0 auto;
      }
      .beamstack-mission {
        display: flex;
        flex-direction: column;
        justify-content: center;
        gap: 0.18rem;
        max-width: 42rem;
        min-width: 0;
      }
      .beamstack-mission-main {
        font-size: clamp(0.9rem, 1.35vw, 1.15rem);
        line-height: 1;
        font-weight: 700;
        color: #263246;
        text-transform: uppercase;
      }
      .beamstack-mission-sub {
        font-size: clamp(0.82rem, 1.1vw, 1.0rem);
        line-height: 1.1;
        font-weight: 500;
        color: #5c6678;
      }
      .road-designer-title {
        margin: 1.05rem 0 0.15rem 0;
        font-size: clamp(2.2rem, 4.2vw, 4.8rem);
        line-height: 1.0;
        font-weight: 820;
        letter-spacing: 0;
        color: #202a3a;
      }
      .beamstack-ayah {
        margin: 0.85rem 0 0.95rem 0;
        padding: 0.75rem 1rem;
        border-left: 3px solid #d92727;
        background: rgba(249, 250, 252, 0.82);
      }
      .beamstack-ayah-ar {
        direction: rtl;
        text-align: left;
        font-family: "Amiri", "Scheherazade New", "Times New Roman", serif;
        font-size: clamp(1.05rem, 1.65vw, 1.35rem);
        line-height: 1.8;
        color: #1f2937;
      }
      .beamstack-ayah-meta {
        margin-top: 0.25rem;
        display: flex;
        justify-content: flex-start;
        gap: 1rem;
        flex-wrap: wrap;
        font-size: 0.82rem;
        line-height: 1.35;
        color: #697386;
      }
      .beamstack-app-band {
        margin: 1.0rem 0 1.25rem 0;
        padding: 1.0rem 1.1rem;
        border: 1px solid rgba(49, 64, 86, 0.14);
        border-radius: 8px;
        background: #ffffff;
      }
      .beamstack-app-kicker {
        margin-bottom: 0.35rem;
        font-size: 0.78rem;
        font-weight: 760;
        text-transform: uppercase;
        color: #d92727;
      }
      .beamstack-app-summary {
        max-width: 72rem;
        margin-bottom: 0.85rem;
        font-size: clamp(0.98rem, 1.25vw, 1.12rem);
        line-height: 1.45;
        color: #2e394c;
      }
      .beamstack-flow-grid {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 0.75rem;
      }
      .beamstack-flow-item {
        border-top: 2px solid rgba(217, 39, 39, 0.8);
        padding-top: 0.55rem;
        min-width: 0;
      }
      .beamstack-flow-label {
        font-size: 0.78rem;
        font-weight: 760;
        color: #1f2937;
      }
      .beamstack-flow-text {
        margin-top: 0.22rem;
        font-size: 0.88rem;
        line-height: 1.35;
        color: #697386;
      }
      .beamstack-contact-footer {
        margin: 2.2rem 0 0.5rem 0;
        padding: 1.15rem 1.25rem;
        border-top: 1px solid rgba(49, 64, 86, 0.18);
        border-bottom: 1px solid rgba(49, 64, 86, 0.12);
        background: linear-gradient(90deg, rgba(249, 250, 252, 0.96), #ffffff);
      }
      .beamstack-contact-title {
        margin-bottom: 0.35rem;
        font-size: clamp(1.15rem, 1.7vw, 1.45rem);
        line-height: 1.2;
        font-weight: 800;
        color: #202a3a;
      }
      .beamstack-contact-text {
        max-width: 76rem;
        font-size: 0.98rem;
        line-height: 1.45;
        color: #5c6678;
      }
      .beamstack-contact-note {
        margin-top: 0.45rem;
        font-size: 0.86rem;
        line-height: 1.35;
        color: #d92727;
        font-weight: 700;
      }
      .beamstack-contact-links {
        display: flex;
        gap: 0.65rem;
        flex-wrap: wrap;
        margin-top: 0.85rem;
      }
      .beamstack-contact-link {
        display: inline-flex;
        align-items: center;
        min-height: 2.25rem;
        padding: 0.45rem 0.7rem;
        border: 1px solid rgba(49, 64, 86, 0.16);
        border-radius: 6px;
        color: #202a3a !important;
        text-decoration: none !important;
        font-size: 0.9rem;
        font-weight: 720;
        background: #ffffff;
      }
      .beamstack-contact-link:hover {
        border-color: rgba(217, 39, 39, 0.55);
        color: #d92727 !important;
      }
      .beamstack-software-list {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
        gap: 0.65rem;
        margin-top: 0.75rem;
      }
      .beamstack-software-item {
        padding: 0.7rem 0.8rem;
        border-left: 3px solid rgba(217, 39, 39, 0.8);
        background: rgba(249, 250, 252, 0.82);
      }
      .beamstack-software-item a {
        color: #202a3a !important;
        font-weight: 780;
        text-decoration: none !important;
      }
      .beamstack-software-item a:hover {
        color: #d92727 !important;
      }
      .beamstack-software-desc {
        margin-top: 0.2rem;
        font-size: 0.83rem;
        line-height: 1.35;
        color: #697386;
      }
      @media (max-width: 760px) {
        .beamstack-header {
          align-items: flex-start;
          gap: 0.75rem;
          flex-wrap: wrap;
        }
        .beamstack-divider {
          display: none;
        }
        .beamstack-mission {
          flex-basis: 100%;
        }
        .beamstack-ayah {
          padding: 0.7rem 0.8rem;
        }
        .beamstack-flow-grid {
          grid-template-columns: 1fr;
        }
        .beamstack-contact-footer {
          padding: 1rem 0.85rem;
        }
      }
    </style>
    <header class="beamstack-header" aria-label="BeamStack">
      <div class="beamstack-name">BeamStack</div>
      <div class="beamstack-divider" aria-hidden="true"></div>
      <div class="beamstack-mission">
        <div class="beamstack-mission-main">Software solutions for engineers</div>
        <div class="beamstack-mission-sub">High-level engineering tools accessible to every engineer.</div>
      </div>
    </header>
    <section class="beamstack-ayah" aria-label="Sourate Taha 20:114">
      <div class="beamstack-ayah-ar">
      وَقُل رَّبِّ زِدْنِي عِلْمًا
      </div>
      <div class="beamstack-ayah-meta">
        <span> said The Great Designer : Sourate Taha, 20:114</span>
        <span>« Seigneur, accrois-moi en science. »</span>
      </div>
    </section>
    <div class="road-designer-title">Road Designer V 1.0</div>
    """,
    unsafe_allow_html=True,
)
st.caption(
    "Génération de livrables BET (DXF + XLSX + PDF) à partir d'un fichier "
    "axe et d'un MNT. Standards REFT (Maroc). Toutes les annotations sont en "
    "français."
)

st.markdown(
    """
    <section class="beamstack-app-band" aria-label="Road Designer workflow">
      <div class="beamstack-app-kicker">Outil métier pour bureaux d'études</div>
      <div class="beamstack-app-summary">
        Road Designer transforme un axe en plan et un MNT en livrables prêts à relire :
        plan, profil en long, profils en travers, cubatures, Bruckner, Excel et PDFs.
        BeamStack construit ce type d'outils pour rendre les workflows d'ingénierie
        de haut niveau accessibles aux petites équipes comme aux grandes structures.
      </div>
      <div class="beamstack-flow-grid">
        <div class="beamstack-flow-item">
          <div class="beamstack-flow-label">1. Entrées</div>
          <div class="beamstack-flow-text">Axe TXT, terrain CSV, catégorie REFT et cartouche.</div>
        </div>
        <div class="beamstack-flow-item">
          <div class="beamstack-flow-label">2. Calcul</div>
          <div class="beamstack-flow-text">Ligne rouge optimisée, profils et cubatures cohérents.</div>
        </div>
        <div class="beamstack-flow-item">
          <div class="beamstack-flow-label">3. Livrables</div>
          <div class="beamstack-flow-text">DXF, XLSX, PDF plan et PDF profils en travers.</div>
        </div>
        <div class="beamstack-flow-item">
          <div class="beamstack-flow-label">4. Idée logicielle</div>
        <div class="beamstack-flow-text">Un workflow répétitif peut devenir un outil métier BeamStack.</div>
        </div>
      </div>
    </section>
    """,
    unsafe_allow_html=True,
)

beamstack_contact = BeamStackContact()


# ─────────────────────────────────────────────────────────────────────────────
# Sidebar — inputs + configuration
# ─────────────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.header("1. Données d'entrée")

    axe_mode = st.radio(
        "Axe en plan",
        ("Exemple bundle", "Charger un TXT"),
        index=0,
        help="Fichier axe au format texte : station de départ, segments D, courbes C.",
    )
    use_sample_axe = axe_mode == "Exemple bundle"
    axe_upload = None
    if not use_sample_axe:
        axe_upload = st.file_uploader(
            "Fichier axe en plan (.txt)",
            type=["txt"],
            help="Format attendu : PK X Y, puis blocs D/C avec stations d'arrivée.",
        )

    with st.expander("Voir un exemple de fichier axe", expanded=not use_sample_axe):
        st.caption("Les 4 premières lignes du fichier d'exemple montrent la forme attendue :")
        axe_example = "\n".join(
            sample_axe_path().read_text(encoding="utf-8").splitlines()[:4]
        )
        st.code(axe_example, language="text")
        st.caption(
            "Ligne 1 : PK X Y. Les blocs D décrivent les segments droits ; "
            "les blocs C décrivent les courbes avec centre XC/YC et rayon R."
        )

    st.download_button(
        "Télécharger l'exemple axe TXT",
        data=sample_axe_bytes(),
        file_name="sample_axe.txt",
        mime="text/plain",
        use_container_width=True,
    )

    st.markdown("---")
    terrain_mode = st.radio(
        "Terrain (MNT)",
        ("Exemple bundle", "Charger un CSV X,Y,Z", "Générer synthétique"),
        index=0,
    )
    terrain_upload = None
    if terrain_mode == "Charger un CSV X,Y,Z":
        terrain_upload = st.file_uploader("Terrain CSV", type=["csv"])

    st.download_button(
        "Télécharger l'exemple terrain CSV",
        data=sample_terrain_bytes(),
        file_name="sample_terrain.csv",
        mime="text/csv",
        use_container_width=True,
    )

    if terrain_mode == "Générer synthétique":
        st.caption("Génère un MNT plausible autour de l'axe.")
        synth = {
            "z_base":     st.number_input("Z de base [m]",     value=780.0),
            "slope_long": st.number_input("Pente longitudinale [fraction]",
                                          value=0.02, format="%.4f"),
            "amplitude":  st.number_input("Amplitude collines [m]", value=4.0),
            "wavelength": st.number_input("Longueur d'onde [m]", value=600.0),
            "noise_sigma": st.number_input("Bruit σ [m]", value=0.4),
            "extent":     st.number_input("Étendue ± [m]", value=60.0),
        }
    else:
        synth = None

    st.markdown("---")
    st.header("2. Catégorie REFT")
    cat = st.selectbox(
        "Catégorie de route", ("CAT_1", "CAT_2", "CAT_3"),
        format_func=lambda c: {
            "CAT_1": "CAT 1 — 80-100 km/h",
            "CAT_2": "CAT 2 — 60-80 km/h",
            "CAT_3": "CAT 3 — 40-60 km/h",
        }[c],
    )
    base_cfg = get_preset(cat)

    st.header("3. Paramètres de conception")
    with st.expander("Géométrie horizontale", expanded=True):
        road_width = st.number_input(
            "Largeur de chaussée - plan et section type [m]",
            value=float(base_cfg.road_width), step=0.5,
            help="Une seule largeur est utilisée pour les bords en plan, les profils en travers et les cubatures.",
        )
        profile_sampling = st.number_input(
            "Pas d'échantillonnage [m]",
            value=float(base_cfg.profile_sampling), step=0.5,
        )

    with st.expander("Ligne rouge — minima REFT", expanded=True):
        r_summit = st.number_input("R minimum sommet [m]",
                                   value=float(base_cfg.r_summit), step=100.0)
        r_sag = st.number_input("R minimum cuvette [m]",
                                value=float(base_cfg.r_sag), step=100.0)
        max_radius = st.number_input("R plafond [m]",
                                     value=float(base_cfg.max_radius),
                                     step=500.0)
        max_pente = st.number_input("Pente maximale [%]",
                                    value=float(base_cfg.max_pente), step=0.5)
        min_tangent_length = st.number_input(
            "Longueur min entre PVI [m]",
            value=float(base_cfg.min_tangent_length), step=10.0,
            help="Distance horizontale minimale entre deux points "
                 "d'intersection verticaux."
        )
        min_straight_tangent = st.number_input(
            "Longueur min de tangente droite entre courbes [m]",
            value=float(base_cfg.min_straight_tangent), step=5.0,
            help="Nouveau dans la V 1.0. Distance droite entre la fin "
                 "d'une courbe verticale et le début de la suivante."
        )
        max_grade_change = st.number_input(
            "Seuil de création de PVI [fraction]",
            value=float(base_cfg.max_grade_change), step=0.001,
            format="%.4f",
        )
        vertical_band_ratio = st.slider(
            "Bande verticale d'optimisation",
            min_value=0.02, max_value=0.40,
            value=float(base_cfg.vertical_band_ratio), step=0.01,
            help="Fraction de l'amplitude TN dans laquelle SLSQP peut "
                 "déplacer chaque PVI."
        )

    with st.expander("Section type / cubatures"):
        chaussee_width = road_width
        st.caption(
            f"Largeur de chaussée utilisée pour la section type : {chaussee_width:.2f} m "
            "(définie dans « Géométrie horizontale »)."
        )
        crown_slope = st.number_input(
            "Dévers normal [%]",
            value=float(base_cfg.typical_section.crown_slope) * 100.0,
            step=0.1,
        )
        accotement_width = st.number_input(
            "Largeur accotement [m]",
            value=float(base_cfg.typical_section.accotement_width), step=0.1,
        )
        accotement_slope = st.number_input(
            "Pente accotement [%]",
            value=float(base_cfg.typical_section.accotement_slope) * 100.0,
            step=0.1,
        )
        ditch_depth = st.number_input(
            "Profondeur fossé [m]",
            value=float(base_cfg.typical_section.ditch_depth), step=0.1,
        )
        ditch_width = st.number_input(
            "Largeur fossé [m]",
            value=float(base_cfg.typical_section.ditch_width), step=0.1,
        )
        talus_deblai = st.number_input(
            "Talus déblai H/V",
            value=float(base_cfg.typical_section.talus_deblai_h_v),
            step=0.05, format="%.3f",
        )
        talus_remblai = st.number_input(
            "Talus remblai H/V",
            value=float(base_cfg.typical_section.talus_remblai_h_v),
            step=0.05, format="%.3f",
        )
        cross_section_step_pk = st.number_input(
            "Profils en travers : tous les N profils",
            value=int(base_cfg.cross_section_step_pk), step=1, min_value=1,
        )
        # Default extent = 1.5 × road_width per side (= 3× road_width total).
        # Prefill the auto-computed default so the user sees the actual
        # value the drawing will use. Mettre 0 pour repasser à l'auto.
        default_extent = (base_cfg.cross_section_extent
                          if base_cfg.cross_section_extent is not None
                          else road_width * 1.5)
        cross_section_extent = st.number_input(
            "Étendue PT ± [m]  (défaut = 1.5 × largeur de chaussée)",
            value=float(default_extent), step=0.5, min_value=0.0,
            help="Demi-largeur du profil en travers. Total dessiné = 2 × "
                 "cette valeur. Le défaut donne un total de 3 × largeur "
                 "de chaussée.",
        )

    with st.expander("Mise en page / PDF", expanded=True):
        sheet_length_pk = st.number_input(
            "Longueur par planche A1 [m]",
            value=float(base_cfg.sheet_length_pk), step=50.0,
            help="Pilote le PDF plan_par_sections.pdf : une page par tranche."
        )
        h_scale = st.number_input("Échelle H DXF (multiplicateur drawing)",
                                  value=float(base_cfg.h_scale), step=0.1)
        v_scale = st.number_input("Échelle V DXF (exagération)",
                                  value=float(base_cfg.v_scale), step=1.0)
        pdf_dpi = st.slider("PDF DPI", 100, 400,
                            value=int(base_cfg.pdf_dpi), step=50)

        st.markdown("---")
        st.markdown("**Échelles PDF — Profil en long (plan_par_sections.pdf)**")
        st.caption("Laisser à 0 pour conserver l'auto-ajustement à la page "
                   "(rendu actuel validé).")
        col1, col2 = st.columns(2)
        with col1:
            pdf_plan_h = st.number_input("Échelle H : 1 / N", min_value=0,
                                         value=0, step=100, key="plan_h",
                                         help="Ex. 1000 → 1 m = 1 mm sur papier")
        with col2:
            pdf_plan_v = st.number_input("Échelle V : 1 / N", min_value=0,
                                         value=0, step=10, key="plan_v",
                                         help="Ex. 100 → 1 m = 10 mm sur papier (×10 exag)")

        st.markdown("**Échelles PDF — Profils en travers (profils_en_travers.pdf)**")
        st.caption(
            "Valeurs par défaut : **H 1:100 — V 1:25** (page A4 portrait, "
            "≈ ×4 d'exagération verticale). "
            "Si les données sont trop hautes pour A4 à 1:25, l'échelle V "
            "est ajustée et un avis est ajouté au pied de page. "
            "Mettre 0 pour repasser à l'auto-ajustement."
        )
        col3, col4 = st.columns(2)
        with col3:
            pdf_pt_h = st.number_input(
                "Échelle H : 1 / N",
                min_value=0,
                value=int(base_cfg.pdf_pt_h_scale or 0),
                step=10, key="pt_h",
                help="Ex. 100 → 1 m = 10 mm sur papier",
            )
        with col4:
            pdf_pt_v = st.number_input(
                "Échelle V : 1 / N",
                min_value=0,
                value=int(base_cfg.pdf_pt_v_scale or 0),
                step=5, key="pt_v",
                help="Ex. 25 → 1 m = 40 mm sur papier "
                     "(≈ ×4 exag avec H=100)",
            )

    with st.expander("Cartouche", expanded=True):
        st.markdown("**Identité de l'entreprise (obligatoire)** —"
                    " s'affiche en en-tête de chaque page PDF.")
        cart_company = st.text_input(
            "Nom de l'entreprise ★",
            help="Apparaît en gros en haut de chaque page PDF.",
        )
        if not cart_company.strip():
            st.warning("⚠️  Le nom de l'entreprise est requis pour générer les PDFs.")
        cart_projet = st.text_input("Projet")
        cart_mo = st.text_input("Maître d'ouvrage")
        cart_bet = st.text_input("BET",
                                 help="Bureau d'études responsable. Peut "
                                      "différer de l'entreprise.")
        cart_designer = st.text_input("Concepteur")
        cart_plan_n = st.text_input("N° de plan", value="PLAN")
        cart_indice = st.text_input("Indice", value="A")
        cart_date = st.text_input("Date", value="")
        cart_ech_h = st.text_input("Échelle H", value=base_cfg.cartouche.echelle_h)
        cart_ech_v = st.text_input("Échelle V", value=base_cfg.cartouche.echelle_v)


# ─────────────────────────────────────────────────────────────────────────────
# Build the DesignConfig from the sidebar
# ─────────────────────────────────────────────────────────────────────────────

ts = TypicalSection(
    chaussee_width=chaussee_width,
    crown_slope=crown_slope / 100.0,
    accotement_width=accotement_width,
    accotement_slope=accotement_slope / 100.0,
    ditch_depth=ditch_depth,
    ditch_width=ditch_width,
    talus_deblai_h_v=talus_deblai,
    talus_remblai_h_v=talus_remblai,
)
cart = CartoucheInfo(
    company_name=cart_company.strip(),
    projet=cart_projet,
    maitre_ouvrage=cart_mo,
    bet=cart_bet,
    designer=cart_designer,
    plan_n=cart_plan_n,
    indice=cart_indice,
    date=cart_date,
    echelle_h=cart_ech_h,
    echelle_v=cart_ech_v,
)
cfg = replace(
    base_cfg,
    road_width=road_width,
    profile_sampling=profile_sampling,
    r_summit=r_summit, r_sag=r_sag, max_radius=max_radius,
    max_pente=max_pente, min_tangent_length=min_tangent_length,
    min_straight_tangent=min_straight_tangent,
    max_grade_change=max_grade_change,
    vertical_band_ratio=vertical_band_ratio,
    h_scale=h_scale, v_scale=v_scale,
    sheet_length_pk=sheet_length_pk,
    cross_section_step_pk=int(cross_section_step_pk),
    cross_section_extent=cross_section_extent,
    pdf_dpi=int(pdf_dpi),
    pdf_plan_h_scale=(int(pdf_plan_h) if pdf_plan_h > 0 else None),
    pdf_plan_v_scale=(int(pdf_plan_v) if pdf_plan_v > 0 else None),
    pdf_pt_h_scale=(int(pdf_pt_h) if pdf_pt_h > 0 else None),
    pdf_pt_v_scale=(int(pdf_pt_v) if pdf_pt_v > 0 else None),
    typical_section=ts,
    cartouche=cart,
)


# ─────────────────────────────────────────────────────────────────────────────
# Main area
# ─────────────────────────────────────────────────────────────────────────────

tab_run, tab_table, tab_preview, tab_contact, tab_help = st.tabs(
    [
        "▶️ Calcul + téléchargements",
        "📋 Tableau",
        "🖼️ Aperçus",
        "💡 Idée de logiciel",
        "📚 Aide",
    ]
)

with tab_help:
    p = _REPO_ROOT / "docs" / "INPUT_FORMAT.md"
    if p.exists():
        st.markdown(p.read_text(encoding="utf-8"))
    else:
        st.info("docs/INPUT_FORMAT.md introuvable.")


with tab_contact:
    st.subheader("Vous avez une idée de logiciel d'ingénierie ?")
    st.write(
        "Décrivez le calcul, le document ou le workflow que vous répétez souvent. "
        "Cette fiche prépare un brief clair à transmettre à BeamStack."
    )

    with st.form("beamstack_idea_form"):
        col_idea_a, col_idea_b = st.columns(2)
        with col_idea_a:
            idea_name = st.text_input("Nom du projet ou de l'organisme")
            contact_ref = st.text_input("Contact à rappeler")
            domain = st.selectbox(
                "Domaine",
                (
                    "Routes / VRD",
                    "Structure",
                    "Hydraulique",
                    "Topographie",
                    "Géotechnique",
                    "Autre workflow d'ingénierie",
                ),
            )
        with col_idea_b:
            current_tools = st.text_input(
                "Outils actuels",
                placeholder="Excel, AutoCAD, Civil 3D, scripts, calcul manuel...",
            )
            expected_output = st.text_input(
                "Livrable attendu",
                placeholder="PDF, DXF, XLSX, rapport, tableau de contrôle...",
            )
            urgency = st.selectbox(
                "Priorité",
                ("Exploration", "Prototype rapide", "Projet à cadrer", "Besoin urgent"),
            )

        workflow_problem = st.text_area(
            "Workflow à transformer en logiciel",
            placeholder=(
                "Exemple : je saisis des données terrain, je refais les mêmes "
                "calculs, puis je prépare un rapport et des plans..."
            ),
            height=130,
        )
        success_criteria = st.text_area(
            "À quoi ressemble une bonne solution ?",
            placeholder=(
                "Exemple : moins d'erreurs, génération automatique des livrables, "
                "contrôles normatifs, interface simple pour l'équipe..."
            ),
            height=100,
        )
        submitted_idea = st.form_submit_button("Préparer le brief")

    if submitted_idea:
        brief = "\n".join(
            [
                "Brief idée logicielle - BeamStack",
                "",
                f"Projet / organisme : {idea_name or '-'}",
                f"Contact : {contact_ref or '-'}",
                f"Domaine : {domain}",
                f"Outils actuels : {current_tools or '-'}",
                f"Livrable attendu : {expected_output or '-'}",
                f"Priorité : {urgency}",
                "",
                "Workflow à transformer :",
                workflow_problem or "-",
                "",
                "Critères de réussite :",
                success_criteria or "-",
            ]
        )
        st.success("Brief préparé.")
        st.text_area("Brief à envoyer à BeamStack", brief, height=300)
        st.download_button(
            "Télécharger le brief TXT",
            data=brief.encode("utf-8"),
            file_name="brief_idee_logiciel_beamstack.txt",
            mime="text/plain",
            use_container_width=True,
        )


# Persist result between reruns
if "result" not in st.session_state:
    st.session_state.result = None
    st.session_state.tmpdir = None


with tab_run:
    col_a, col_b = st.columns([2, 1])
    with col_a:
        st.subheader("Préparation des fichiers")
        if use_sample_axe:
            st.success("Axe : sample_axe.txt (bundle)")
        elif axe_upload is None:
            st.warning("Aucun axe chargé.")
        else:
            st.success(f"Axe chargé : {axe_upload.name}")

        if terrain_mode == "Exemple bundle":
            st.success("Terrain : sample_terrain.csv (bundle)")
        elif terrain_mode == "Charger un CSV X,Y,Z" and terrain_upload is None:
            st.warning("Aucun terrain CSV chargé.")
        elif terrain_mode == "Charger un CSV X,Y,Z":
            st.success(f"Terrain chargé : {terrain_upload.name}")
        else:
            st.info("Terrain synthétique sera généré à partir de l'axe.")

    with col_b:
        company_ok = bool(cart_company.strip())
        axe_ok = use_sample_axe or axe_upload is not None
        terrain_ok = (
            terrain_mode == "Exemple bundle"
            or terrain_mode == "Générer synthétique"
            or terrain_upload is not None
        )
        ready_to_run = company_ok and axe_ok and terrain_ok
        missing = []
        if not company_ok:
            missing.append("nom de l'entreprise")
        if not axe_ok:
            missing.append("fichier axe en plan")
        if not terrain_ok:
            missing.append("CSV terrain")
        run = st.button(
            "🚀 Générer", type="primary", use_container_width=True,
            disabled=not ready_to_run,
            help=("" if ready_to_run
                  else "Renseignez : " + ", ".join(missing) + "."),
        )

    if run:
        # Resolve axe path
        tmpdir = tempfile.mkdtemp(prefix="road_designer_")
        st.session_state.tmpdir = tmpdir
        tmp = Path(tmpdir)

        if use_sample_axe:
            axe_path = sample_axe_path()
        elif axe_upload is None:
            st.error("Veuillez charger un fichier axe.")
            st.stop()
        else:
            axe_path = tmp / "axe.txt"
            axe_path.write_bytes(axe_upload.getvalue())

        # Resolve terrain path
        if terrain_mode == "Exemple bundle":
            terrain_path = sample_terrain_path()
        elif terrain_mode == "Charger un CSV X,Y,Z":
            if terrain_upload is None:
                st.error("Veuillez charger un CSV terrain.")
                st.stop()
            terrain_path = tmp / "terrain.csv"
            terrain_path.write_bytes(terrain_upload.getvalue())
        else:
            terrain_path = tmp / "terrain_synth.csv"
            with st.spinner("Génération du terrain synthétique…"):
                generate_synthetic_terrain(axe_path, terrain_path, **synth)
            st.success(f"Terrain synthétique généré ({terrain_path.name}).")

        with st.spinner("Calcul du design + assemblage DXF/XLSX/PDF…"):
            try:
                result = build_design(cfg, axe_path, terrain_path, tmp / "out")
            except Exception as exc:
                st.exception(exc)
                st.stop()
        st.session_state.result = result
        st.success("Build terminé.")

    # Download buttons (visible once a result exists)
    r = st.session_state.result
    if r is not None:
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.download_button(
                "⬇️ DXF", data=Path(r["dxf"]).read_bytes(),
                file_name=cfg.dxf_filename,
                mime="application/dxf", use_container_width=True,
            )
        with c2:
            st.download_button(
                "⬇️ XLSX", data=Path(r["xlsx"]).read_bytes(),
                file_name=cfg.xlsx_filename,
                mime=("application/vnd.openxmlformats-officedocument."
                      "spreadsheetml.sheet"),
                use_container_width=True,
            )
        with c3:
            st.download_button(
                "⬇️ PDF Plan", data=Path(r["pdf_plan"]).read_bytes(),
                file_name=cfg.pdf_plan_filename,
                mime="application/pdf", use_container_width=True,
            )
        with c4:
            st.download_button(
                "⬇️ PDF Profils en travers", data=Path(r["pdf_pt"]).read_bytes(),
                file_name=cfg.pdf_pt_filename,
                mime="application/pdf", use_container_width=True,
            )

        if r["warnings"]:
            st.warning(
                f"{len(r['warnings'])} avertissement(s) REFT — "
                "voir l'onglet 'Avertissements REFT' du fichier Excel."
            )
            with st.expander("Voir la liste"):
                for w in r["warnings"]:
                    st.write(f"• {w}")


with tab_table:
    r = st.session_state.result
    if r is None:
        st.info("Lancez d'abord un calcul depuis l'onglet « Calcul + téléchargements ».")
    else:
        import pandas as pd
        df = pd.read_excel(r["xlsx"], sheet_name="Profil en long")
        st.dataframe(df, use_container_width=True, hide_index=True)


with tab_preview:
    r = st.session_state.result
    if r is None:
        st.info("Aperçus disponibles après calcul.")
    else:
        st.subheader("Profil en long + projet")
        from road_designer.config import get_preset as _gp
        # We re-load the design just to draw a quick matplotlib preview.
        # In a future iteration this should reuse the in-memory RoadDesign.
        st.caption("Aperçu rapide. La version complète est dans le DXF / PDF.")
        # Re-derive from XLSX since we don't keep the RoadDesign in session
        import pandas as pd
        df = pd.read_excel(r["xlsx"], sheet_name="Profil en long")
        fig, ax = plt.subplots(figsize=(11, 4))
        ax.plot(df["PK (m)"], df["Cote TN (m)"], color="green", label="TN")
        ax.plot(df["PK (m)"], df["Cote Projet (m)"], color="red", label="Projet")
        ax.fill_between(df["PK (m)"], df["Cote TN (m)"], df["Cote Projet (m)"],
                        where=(df["Cote Projet (m)"] >= df["Cote TN (m)"]),
                        color="lightgreen", alpha=0.4, label="Remblai")
        ax.fill_between(df["PK (m)"], df["Cote TN (m)"], df["Cote Projet (m)"],
                        where=(df["Cote Projet (m)"] <  df["Cote TN (m)"]),
                        color="lightcoral", alpha=0.4, label="Déblai")
        ax.set_xlabel("PK (m)"); ax.set_ylabel("Cote (m)")
        ax.grid(True, alpha=0.3); ax.legend(loc="best")
        st.pyplot(fig)

        st.subheader("Diagramme de Bruckner")
        fig2, ax2 = plt.subplots(figsize=(11, 3))
        ax2.plot(df["PK (m)"], df["Bruckner M(PK) (m³)"], color="purple")
        ax2.axhline(0, color="black", linewidth=0.6)
        ax2.fill_between(df["PK (m)"], df["Bruckner M(PK) (m³)"], 0,
                         where=(df["Bruckner M(PK) (m³)"] >= 0),
                         color="lightgreen", alpha=0.4)
        ax2.fill_between(df["PK (m)"], df["Bruckner M(PK) (m³)"], 0,
                         where=(df["Bruckner M(PK) (m³)"] <  0),
                         color="lightcoral", alpha=0.4)
        ax2.set_xlabel("PK (m)"); ax2.set_ylabel("M(PK) [m³]")
        ax2.grid(True, alpha=0.3)
        st.pyplot(fig2)


software_links_html = "\n".join(
    (
        '<div class="beamstack-software-item">'
        f'<a href="{link.url}" target="_blank" rel="noopener noreferrer">{link.name}</a>'
        f'<div class="beamstack-software-desc">{link.description}</div>'
        '</div>'
    )
    for link in beamstack_contact.software_links
)

st.markdown(
    f"""
    <footer class="beamstack-contact-footer" aria-label="Contact BeamStack">
      <div class="beamstack-contact-title">Un logiciel métier à construire ?</div>
      <div class="beamstack-contact-text">
        Si vous avez une idée de logiciel, un problème technique à résoudre
        ou un workflow répétitif qui prend trop de temps, contactez BeamStack.
        Nous transformons vos méthodes, calculs et livrables en outils
        professionnels, clairs et accessibles.
      </div>
      <div class="beamstack-contact-links">
        <a class="beamstack-contact-link" href="mailto:{beamstack_contact.email}">
          Contact : {beamstack_contact.email}
        </a>
      </div>
      <div class="beamstack-contact-note">Voir nos logiciels</div>
      <div class="beamstack-software-list">
        {software_links_html}
      </div>
      <div class="beamstack-contact-note">
        Décrivez votre besoin dans l'onglet « Idée de logiciel » :
        nous le construirons pour vous.
      </div>
    </footer>
    """,
    unsafe_allow_html=True,
)
