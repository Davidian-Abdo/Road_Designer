"""Road Designer V 1.0 — Streamlit Community Cloud UI.

Entry point that any user of the deployed app sees. Three principles:

  1. **No writes outside tempfile**. Outputs are streamed via st.download_button.
  2. **No hard-coded paths**. Samples are resolved via samples_api.
  3. **Every DesignConfig knob exposed**. Sidebar drives the dataclass.

Run locally with:  ``streamlit run app.py``
"""
from __future__ import annotations

import io
import tempfile
from dataclasses import replace
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import streamlit as st

from road_designer.config import (
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

st.title("🛣️ Road Designer V 1.0")
st.caption(
    "Génération de livrables BET (DXF + XLSX + PDF) à partir d'un fichier "
    "axe et d'un MNT. Standards REFT (Maroc). Toutes les annotations sont en "
    "français."
)


# ─────────────────────────────────────────────────────────────────────────────
# Sidebar — inputs + configuration
# ─────────────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.header("1. Données d'entrée")

    use_sample_axe = st.checkbox("Utiliser l'axe d'exemple", value=True,
                                 help="samples/sample_axe.txt")
    axe_upload = (None if use_sample_axe
                  else st.file_uploader("Fichier axe (.txt)", type=["txt"]))

    st.markdown("---")
    terrain_mode = st.radio(
        "Terrain (MNT)",
        ("Exemple bundle", "Charger un CSV X,Y,Z", "Générer synthétique"),
        index=0,
    )
    terrain_upload = None
    if terrain_mode == "Charger un CSV X,Y,Z":
        terrain_upload = st.file_uploader("Terrain CSV", type=["csv"])

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
            "Largeur de chaussée [m]",
            value=float(base_cfg.road_width), step=0.5,
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
        chaussee_width = st.number_input(
            "Largeur chaussée (section type) [m]",
            value=float(base_cfg.typical_section.chaussee_width), step=0.5,
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
            "Valeurs par défaut : **H 1:100 — V 1:15** (page A4 portrait, "
            "≈ ×6.7 d'exagération verticale). "
            "Si les données sont trop hautes pour A4 à 1:15, l'échelle V "
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
                help="Ex. 15 → 1 m = 66.7 mm sur papier "
                     "(≈ ×6.7 exag avec H=100)",
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

tab_run, tab_table, tab_preview, tab_help = st.tabs(
    ["▶️ Calcul + téléchargements", "📋 Tableau", "🖼️ Aperçus", "📚 Aide"]
)

with tab_help:
    p = Path(__file__).parent / "docs" / "INPUT_FORMAT.md"
    if p.exists():
        st.markdown(p.read_text(encoding="utf-8"))
    else:
        st.info("docs/INPUT_FORMAT.md introuvable.")


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
        run = st.button(
            "🚀 Générer", type="primary", use_container_width=True,
            disabled=not company_ok,
            help=("" if company_ok
                  else "Renseignez d'abord le nom de l'entreprise."),
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
            axe_path.write_bytes(axe_upload.read())

        # Resolve terrain path
        if terrain_mode == "Exemple bundle":
            terrain_path = sample_terrain_path()
        elif terrain_mode == "Charger un CSV X,Y,Z":
            if terrain_upload is None:
                st.error("Veuillez charger un CSV terrain.")
                st.stop()
            terrain_path = tmp / "terrain.csv"
            terrain_path.write_bytes(terrain_upload.read())
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
