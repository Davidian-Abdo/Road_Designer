# LinkedIn — Road Designer V 1.0 launch post

One single piece, calibrated for LinkedIn's algorithm: opens with a short pattern-interrupt line that begs the click on "*… voir plus*", body in scannable chunks, ends with a clear call-to-action. Replace `[lien]` with your repo URL before posting. Hashtags are at the bottom so the algorithm picks them up without breaking the read.

---

🛣️ **Combien d'heures votre BET passe-t-il à monter un dossier de tracé routier avant signature ?**

Réponse honnête : trop.

À chaque section de route, le même rituel revient :
importer le MNT, tracer la ligne rouge à la main en respectant les minima REFT, calculer les cubatures, dessiner trente profils en travers, monter les planches A1 au cartouche, exporter en DXF, exporter en PDF, relire, recommencer.

Chaque cycle : une demi-journée.
Chaque révision du tracé : encore une demi-journée.

Alors j'ai construit **Road Designer V 1.0** — l'outil que j'aurais voulu avoir comme ingénieur débutant.

À partir de **deux fichiers** :
🗂️ un axe au format BET marocain (segments droits + courbes circulaires)
🗂️ un MNT en CSV (X, Y, Z)

… et d'un nom d'entreprise, l'outil produit en moins d'une minute :

📄 Un **DXF complet** — tracé en plan, profil en long, tableau à 7 lignes (avec cubatures par segment et cumulées), diagramme des courbures, diagramme de Bruckner annoté aux extrema. Indexé sur PK, sans le bug classique du « profil X = X tourné ».

📊 Un **Excel** à 12 colonnes — PK, distances, cotes TN/projet, h, pente, V_déblai et V_remblai par segment, V cumulés, M(PK) Bruckner — avec un onglet listant les avertissements REFT (rayon < min, tangente droite < seuil, etc.).

🗺️ Un **PDF Plan + Profil en long** au format A1 paysage, une page par tranche de route configurable (par défaut 500 m), avec **cartouche professionnel** : nom d'entreprise en gros, badge « Dossier de projet », titre projet, blocs informations / cubatures (avec barres horizontales déblai vs remblai) / indice / date / n° de plan.

📏 Un **PDF Profils en travers** au format A4 portrait, une page par profil — section type configurable (chaussée + accotements + fossés + talus), polygones déblai/remblai hachurés, échelles H 1:100 / V 1:25 par défaut (auto-ajustées si les données débordent), en-tête entreprise sur chaque page.

🔬 **Sous le capot** :
La ligne rouge n'est pas tracée à la main — elle est **optimisée par SLSQP** : minimise ∑\|Z_projet − Z_TN\| sous trois contraintes (pente max, rayon minimum sommet/cuvette par REFT, longueur minimum de tangente droite entre deux courbes verticales). Les paraboles symétriques sont sélectionnées avec un rayon par PVI (le maximum praticable, plafonné par REFT). Les cubatures utilisent un vrai split à h = 0 — pas un mélange déblai/remblai dans le même segment.

⚡ **REFT catégories 1, 2 et 3** prédéfinies. Choix de catégorie → minima rayons + pente max chargés automatiquement.

🌐 **Interface web Streamlit** — aucune installation AutoCAD requise. Le concepteur charge son MNT et son axe, ajuste les paramètres dans la barre latérale (catégorie REFT, largeur de chaussée, pentes talus, échelles PDF, cartouche), clique sur Générer, télécharge DXF + XLSX + 2 PDFs.

🧪 **Tests** : 39 tests pytest pinnent la math civile (continuité des paraboles, plancher REFT, identité Bruckner M(fin) = bilan, monotonie PK, scaling V cohérent).

💻 **Open-source** : Python + NumPy + SciPy + ezdxf + matplotlib + Streamlit.
Code, exemples, et documentation des formats d'entrée : [lien]

---

**Pour qui ?**
Bureaux d'études techniques (BET), ingénieurs routiers, services techniques de collectivités. Tout particulièrement les structures qui livrent des avant-projets sommaires et détaillés conformes REFT et qui veulent récupérer leurs après-midis pour faire de la conception au lieu de la mise en page.

**Pour quoi ?**
Avant-projets, études comparatives entre variantes de tracé, vérifications REFT rapides, préparation de dossiers de signature, dimensionnement préliminaire des terrassements. Pas (encore) pour la signature finale d'un dossier d'exécution — c'est l'ingénieur signataire qui valide.

**Roadmap V 1.x**
🔜 Clothoïdes (raccordements progressifs droite ↔ arc)
🔜 Calcul du dévers en courbe + diagramme dévers
🔜 Vérification de distance d'arrêt (SSD)
🔜 Import LandXML / export GeoJSON
🔜 Cataloguage des variantes pour études comparatives

**Vos retours m'intéressent.** Si vous êtes ingénieur dans un BET, dites-moi ce qui vous coûterait le moins de douleur à automatiser ensuite.

👉 [lien]

#GénieCivil #IngénierieCivile #Route #BET #REFT #Maroc #InfrastructureTransport #ConceptionRoutière #DXF #AutoCAD #OpenSource #Python #Streamlit #CivilEngineering #RoadDesign #SLSQP
