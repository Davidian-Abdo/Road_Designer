# Formats d'entrée — Road Designer V 1.0

Ce document décrit les **deux fichiers d'entrée** attendus par l'application :

| Fichier | Description | Exemple bundle |
|---|---|---|
| `axe.txt`     | Tracé en plan (segments droits + courbes circulaires) | `samples/sample_axe.txt` |
| `terrain.csv` | Modèle Numérique de Terrain (semis de points X, Y, Z) | `samples/sample_terrain.csv` |

---

## 1. Le fichier `axe.txt`

### 1.1 Grammaire

Le fichier décrit le tracé sous forme d'une **suite de segments** :

- une **première ligne** donne le point de départ (PK, X, Y) ;
- chaque segment suivant est introduit par un mot-clé :
  - `D{n}` — segment **droit** (ligne droite) ;
  - `C{n}` — segment en **courbe** circulaire ;
- chaque segment est immédiatement suivi de **la station d'arrivée** (PK, X, Y).

```
First line          : PK0    X0    Y0
Straight (segment droit):
  D{n}    GIS = ...   length
  PK   X   Y                              ← station de fin
Curve (courbe circulaire):
  C{n}    XC = xc
          YC = yc
          R  = radius    length           ← rayon signé
  PK   X   Y                              ← station de fin
```

### 1.2 Convention de signe sur R

| Signe de R | Sens de la courbe |
|---|---|
| **+** | virage à gauche (sens trigonométrique) |
| **−** | virage à droite |

### 1.3 Unités

- Distances et coordonnées : **mètres**
- Rayons : **mètres**
- GIS : **grades** — info indicative, non utilisée par le moteur

### 1.4 Exemple annoté

```
               1512.101    447289.137    254023.033   ← P1 : station de départ
                                                        PK = 1512.101 m
                                                        X  = 447 289.137 m (Lambert)
                                                        Y  = 254 023.033 m

 D1     GIS = 254.706g     38.350                     ← Segment droit n° 1, L = 38.35 m
               1550.451    447260.090    253997.992   ← P2 : station de fin du D1

 C1     XC = 447276.414                               ← Courbe circulaire n° 1
        YC = 253979.057                                  Centre (XC, YC)
        R  =     25.000    19.856                        Rayon = 25 m (gauche), L = 19.856 m
               1570.308    447251.467    253980.683   ← P3 : station de fin du C1

 D2     GIS = 204.143g     19.428
               1589.735    447250.203    253961.296

 C2     XC = 447200.309
        YC = 253964.548
        R  =    -50.000    18.203                     ← R négatif → virage à droite
               1607.938    447245.775    253943.743
 …
```

### 1.5 Règles & pièges

1. La **continuité** des stations doit être respectée : la station d'arrivée d'un segment est la station de départ du suivant.
2. La **longueur** donnée sur la ligne `D` ou `R = … L` doit être **cohérente** avec la distance euclidienne entre stations (un avertissement est affiché sinon).
3. Le PK doit être **strictement croissant**.
4. Les chiffres décimaux utilisent le **point** comme séparateur (`25.000`, jamais `25,000`).

---

## 2. Le fichier `terrain.csv`

### 2.1 Structure

Trois colonnes obligatoires, séparées par des virgules :

```
X,Y,Z
447289.137,254023.033,778.853
447286.454,254020.720,778.598
…
```

- **X**, **Y** : coordonnées planimétriques dans le **même CRS** que l'axe (Lambert-Maroc, UTM, ou local — l'application ne reprojette pas).
- **Z** : cote en mètres.

### 2.2 Densité recommandée

| Type de projet | Espacement type | Notes |
|---|---|---|
| Avant-projet sommaire    | 5–10 m  | Restitué à partir d'un DEM SRTM ou photogrammétrie aérienne. |
| Avant-projet détaillé    | 1–5 m   | Levé topographique GPS RTK ou LiDAR. |
| Projet d'exécution       | < 1 m   | Levé terrestre dense. |

Le moteur construit un TIN (Delaunay) à partir des points. **Toute la zone parcourue par l'axe et sa bande transverse (≥ ± `cross_section_extent`) doit être couverte** ; en dehors de l'enveloppe convexe le moteur passe à la "plus proche voisine" et émet un avertissement.

### 2.3 Génération automatique pour tests

Si vous n'avez pas encore de MNT pour la zone, **`samples/synth_terrain.py`** crée un terrain synthétique plausible à partir de votre axe :

```bash
python -m samples.synth_terrain \\
    --axe samples/sample_axe.txt \\
    --out samples/sample_terrain.csv \\
    --z-base 780 \\
    --slope 0.02 \\
    --amplitude 4 \\
    --wavelength 600 \\
    --noise 0.4
```

Le résultat est uniquement un **terrain d'essai** — ne **jamais** s'en servir pour un livrable réel.

---

## 3. Validation rapide

Avant de lancer un calcul long, vérifiez :

```bash
python main.py --axe samples/sample_axe.txt --terrain samples/sample_terrain.csv --out output
```

S'il y a des avertissements REFT (rayon < minimum, pente trop forte, tangente droite trop courte entre deux courbes…), ils sont affichés sur la console et listés dans l'onglet **« Avertissements REFT »** du fichier Excel produit.
