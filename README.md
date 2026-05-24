# Road Designer V 1.0

**Génération automatique de livrables BET pour la conception routière** — du fichier MNT et du tracé en plan jusqu'au DXF, à l'Excel des cubatures et aux deux PDFs prêts à imprimer (plan + profil en long sectionnés A1, profils en travers A3).

Conçu pour les bureaux d'études techniques travaillant aux standards REFT marocains (catégories 1 / 2 / 3) ou équivalents ARP / ICTAAL. Toutes les annotations à l'écran et au plan sont en français.

```
terrain.csv  ─┐
              │   ┌──────────────────────────┐    ┌─ road_design.dxf
axe.txt    ───┼─► │  Road Designer V 1.0    ├─►  ├─ tableau.xlsx
              │   │  (optimisation SLSQP    │    ├─ plan_par_sections.pdf
DesignConfig ─┘   │   + cubatures + PDF)    │    └─ profils_en_travers.pdf
                  └──────────────────────────┘
```

---

## En bref

| Capacité | Détail |
|---|---|
| **Tracé en plan** | Segments droits + arcs circulaires, lecture du fichier axe BET standard (D / C avec XC YC R) |
| **Ligne rouge** | Optimisée par SLSQP — minimise ∑\|Z_projet − Z_TN\| sous contraintes REFT (pente max, rayon min sommet/cuvette, longueur min de tangente droite entre deux courbes verticales) |
| **Courbes verticales** | Paraboles symétriques, K-valeur sélectionnée par PVI (rayon max possible plafonné par REFT) |
| **Cubatures** | Méthode des aires moyennes avec polygones réels issus des profils en travers (Phase 1b) ; déblai et remblai séparés à chaque transition `h = 0` |
| **Diagramme de Bruckner** | `M(PK) = Σ (V_remblai − V_déblai)` annoté aux extrema (frontières naturelles de transport) |
| **Profils en travers** | Section type configurable (chaussée + accotements + fossés + talus) avec pentes H/V par catégorie de talus |
| **Livrables PDF** | Plan + profil en long découpés par tranches de `sheet_length_pk` (A1 paysage) ; un profil en travers par page (A3 portrait par défaut) |
| **Couverture professionnelle** | En-tête entreprise, badge "DOSSIER DE PROJET", titre projet, blocs informations / cubatures (avec barres horizontales) / indice / date / n° de plan |
| **En-tête de page** | Bande supérieure avec nom de l'entreprise (gauche), projet centré, n° de page + date à droite — sur chaque page non-couverture |
| **Standards** | REFT_CAT_1 / CAT_2 / CAT_3 prédéfinis, ou paramètres personnalisés via l'UI |

---

## Démarrage rapide

### 1. Installation

```bash
git clone https://github.com/<your-org>/road-designer.git
cd road-designer
python -m venv .venv
source .venv/bin/activate          # Windows : .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Lancement de l'interface Streamlit (recommandé)

```bash
streamlit run app.py
```

Puis ouvrir `http://localhost:8501`. Charger l'exemple intégré ou ses propres fichiers, ajuster les paramètres dans la barre latérale, cliquer sur **Générer**, et télécharger DXF + XLSX + 2 PDFs.

### 3. Mode ligne de commande

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

Les fichiers sortants atterrissent dans `output/`.

---

## Formats d'entrée

### `axe.txt` — tracé en plan

Format BET marocain classique :

```
        1512.101   447289.137   254023.033        ← PK0  X0  Y0
 D1     GIS = 254.706g     38.350                 ← segment droit, L = 38.35 m
        1550.451   447260.090   253997.992        ← station fin D1

 C1     XC = 447276.414                           ← courbe : centre X
        YC = 253979.057                           ← centre Y
        R  =  25.000        19.856                ← rayon signé, L = 19.856 m
        1570.308   447251.467   253980.683        ← station fin C1
 …
```

Le **signe du rayon** indique le sens : positif = courbe à gauche (trigonométrique), négatif = à droite. Voir `docs/INPUT_FORMAT.md` pour la grammaire complète + un exemple commenté.

### `terrain.csv` — modèle numérique de terrain (MNT)

```
X,Y,Z
447289.137,254023.033,778.853
447286.454,254020.720,778.598
…
```

Trois colonnes, séparées par virgules. Le système de coordonnées (Lambert-Maroc, UTM, ou local) doit être identique à celui de l'axe. Le moteur construit un TIN (Delaunay) et bascule sur la plus proche voisine hors enveloppe convexe.

Densité recommandée : 1 à 5 m pour un avant-projet détaillé, 5 à 10 m pour un avant-projet sommaire.

### Génération automatique d'un MNT d'essai

```bash
python -m samples.synth_terrain \
    --axe samples/sample_axe.txt \
    --out samples/sample_terrain.csv \
    --z-base 780 --slope 0.02 --amplitude 4 --wavelength 600
```

Pour tester l'application sans MNT réel.

---

## Architecture (post-refactor V 1.0)

```
road_designer/
├── config.py          ← @dataclass DesignConfig + REFT_CAT_1/2/3
├── mnt_engine.py      ← TerrainModel (TIN + KDTree fallback)
├── axe_parser.py      ← LineSegment, ArcSegment, AlignmentParser
├── geometry_engine.py ← normal, offset, rotation
├── design_logic.py    ← VerticalAlignment (paraboles)
├── road_design.py     ← RoadDesign orchestrator + build_design()
├── cross_section.py   ← TypicalSection + CrossSectionDrawer (polygones cut/fill)
├── cubature.py        ← aires plateforme + Bruckner
├── dxf_export.py      ← assemblage DXF complet (modelspace + paperspace)
├── excel_export.py    ← XLSX 12 colonnes + onglet REFT warnings
├── pdf_direct.py      ← PDF vectoriel matplotlib (cover BET + headers)
└── samples_api.py     ← accès aux exemples et terrain synthétique

samples/               ← fichiers d'exemple bundle
docs/INPUT_FORMAT.md   ← grammaire des entrées
tests/                 ← suite pytest (39 tests)
app.py                 ← interface Streamlit
main.py                ← CLI
CLAUDE.md              ← référence pour les sessions de maintenance
```

Voir [`CLAUDE.md`](CLAUDE.md) pour la description détaillée du pipeline, le vocabulaire civil engineering, la convention des layers DXF, et le contrat PDF.

---

## Échelles par défaut

| PDF | Page | H | V | Exagération verticale |
|---|---|---|---|---|
| Plan + profil en long (`plan_par_sections.pdf`) | A1 paysage | auto-ajusté (~1:700-1:1000) | auto (~1:70-1:100) | ≈ ×10 |
| Profils en travers (`profils_en_travers.pdf`) | A4 portrait | **1:100** | **1:15** | ≈ ×6.7 |

Les quatre échelles (deux par PDF) sont **modifiables via l'UI** (champ « Mise en page / PDF »). Mettre 0 pour repasser à l'auto-ajustement.

L'étendue latérale des profils en travers vaut par défaut **1.5 × largeur de chaussée par côté** (total = 3 × largeur de chaussée). Pour une chaussée de 7 m → ± 10.5 m → 21 m total dessiné. Modifiable via le champ « Étendue PT ± ».

**Auto-ajustement A4** — si les échelles H/V forcées par l'utilisateur produisent un dessin plus grand que la zone utile A4 (200 × 235 mm), le renderer abaisse automatiquement les échelles affectées pour faire tenir le dessin sur la page. Le pied de page indique alors « *échelle ajustée pour A4* » et reporte les échelles réellement obtenues. Pour une chaussée de 7 m avec un h ≈ 4 m de déblai/remblai, les défauts produisent un dessin d'environ **200 × 235 mm** (95 % × 79 % de l'A4 utile).

---

## Tests

```bash
pytest tests/ -v
```

39 tests pinnent : grammaire de l'axe, continuité des paraboles, signe sommet/cuvette, plancher REFT, partage `h = 0` dans la cubature, identités de Bruckner, géométrie 2D, calage profil/plan, sélection des échelles PT, validation `company_name`, et 5 tests de mise en page (profil sous le plan, monotonie PK, échelle V cohérente).

---

## Conventions

- **Unités** : mètres et degrés ; les pentes sont stockées en fractions (0.06 = 6 %) et affichées en % aux frontières (UI / DXF).
- **Indépendante de PK** : profil, tableau, Bruckner et cubatures sont tous indexés par PK. La rotation du plan vers l'axe début-fin sert uniquement à l'affichage et ne se propage jamais aux calculs.
- **Layers DXF** : `AXIS / EDGES / GROUND / PROJECT / TABLE / TABLE_TEXT / TABLE_CUBATURE / HAUTEURS_REM / HAUTEURS_DEB / RAPPEL / BUBBLES / CUTTING_LINES / CURV_DIAG / BRUCKNER / PT_* / CARTOUCHE`. Aucune entité n'est dessinée sur le layer 0.
- **Sortie** : `output/` est gitignored. La couche Streamlit n'écrit jamais à la racine du dépôt — tout passe par `tempfile.TemporaryDirectory` puis `st.download_button`.

---

## Licence et standards

Standards de référence : [REFT — Recueil d'Études Techniques Fondamentales (Maroc)](https://www.equipement.gov.ma/) catégories 1, 2 et 3. Pour la France, les paramètres correspondent grosso modo à ICTAAL / ICTAVRU ; en cas de doute, vérifier les minima de votre cahier des charges.

Cet outil **n'est pas certifié pour signature** : il produit des avant-projets et des livrables intermédiaires que l'ingénieur signataire doit relire et valider.

---

## Roadmap V 1.x

- [ ] Clothoïdes (raccordements progressifs entre droite et arc circulaire)
- [ ] Calcul du dévers en courbe avec diagramme dédié
- [ ] Vérification de visibilité (distance d'arrêt SSD)
- [ ] Import LandXML / export GeoJSON
- [ ] Génération multi-tracés pour études comparatives

Suggestions et issues : voir le dépôt GitHub.
