# Reprendre ColorInk

Notes pour qui veut modifier ou continuer le projet : comment il est construit, pourquoi certains choix ont été faits, et les endroits où une erreur casse quelque chose sans prévenir.
*English version: [CONTRIBUTING.md](CONTRIBUTING.md).*

## Fichiers

| Fichier | Rôle |
|---|---|
| `colorink.py` | Le cœur, sans interface : papier → transparence, détection des zones, palette, export PSD / ORA / PNG. Utilisable seul en ligne de commande. |
| `interface.py` | L'application Gradio (3 colonnes, onglets Aperçu / Guides / Couleurs, export). |
| `textes.py` | Tous les textes de l'interface, en français et en anglais. |
| `editeur_guides.js` | L'éditeur des guides (Fermer / Ouvrir / Exclure / Gomme), dans un composant `gr.HTML`. |
| `peinture.js` | Le pot de peinture, exécuté dans le navigateur. |
| `docs/guide.html` | Le mode d'emploi, généré : ne pas le modifier à la main. |
| `docs/source/` | Le modèle du guide (`modele_guide.html`), ses images et `construire_guide.py`, qui produit `docs/guide.html` avec les images intégrées. |
| `images/` | Logo, icône (`.png` pour Linux et l'onglet du navigateur, `.ico` pour Windows). |
| `polices/` | Police Outfit (SIL OFL 1.1), servie localement. |
| `lancer.sh`, `lancer.command`, `lancer.bat` | Lanceurs uv (Linux / macOS / Windows). Seul `lancer.sh` a été testé, sous Linux. |
| `pyproject.toml`, `.python-version`, `requirements.txt` | Dépendances (uv lit les deux premiers, pip le dernier). |

Après une modification du guide : `python docs/source/construire_guide.py`.

## Le pipeline

```
image → fond du papier estimé → alpha du trait → seuil + guides rouges → fermeture des trous
      → passages verts et exclusions soustraits → composantes connexes → îlots → aplats sous le trait → PSD
```

1. **Papier → transparence** (`fond_papier`, `blanc_vers_alpha`) : le fond est estimé sur une version réduite (800 px) par dilatation, érosion et flou, ce qui corrige ombres et dégradés d'une photo. Alpha = 1 − min(pixel / papier) ; la *balance* agit comme un seuil.
2. **Zones** (`zones`) : le trait seuillé reçoit les guides rouges, puis une dilatation de la taille des trous ; les guides verts et les zones exclues sont retirés. `cv2.connectedComponents` en connectivité 4. Les composantes qui touchent le bord forment l'extérieur ; les trop petites sont ignorées. `expand_labels` (scikit-image) étend les îlots sous le trait pour qu'il n'y ait pas de liseré.
3. **Exclusions** (`zone_entouree`) : le tracé violet est dilaté, puis `binary_fill_holes` donne la surface entourée.
4. **Palette bleue** (`nuances_bleues`, `palette_bleue`) : nuances tirées d'une séquence de Halton, attribuées pour maximiser l'écart (LAB) entre îlots voisins.
5. **Couleurs** : les clics sont gardés en coordonnées relatives `(x, y, rgb)` et réappliqués par `Resultat.aplats(peintures)`, donc ils survivent à un changement de réglage ou de guide.
6. **Export** (`enregistrer`, `ecrire_psd`) : Trait / Aplats (ou un groupe d'un calque par îlot) / Papier, plus les calques d'aide masqués.

## Choix et pièges

**PSD**
- `PSDImage.new("RGBA")` et non `"RGB"` : en RGB, psd-tools ajoute un masque à chaque calque.
- L'image fusionnée est écrite à la main, compressée en RLE. Sans cela, un PSD faisait environ 60 Mo ; avec, 3 à 8 Mo.
- La couleur est mise à zéro sous les pixels entièrement transparents : invisible, mais la compression gagne beaucoup.
- Vérifié dans Krita 5.2 et GIMP 2.10 : tous les calques, aucun masque, calques d'aide masqués, rendu identique (écart maximal de 1 sur 255). À refaire après toute modification de `ecrire_psd`.
- psd-tools ≥ 1.25 exige Python ≥ 3.11.

**Gradio (version 6)**
- Les guides et la peinture sont des composants `gr.HTML` sur mesure (`js_on_load`, `props`). L'interface JS est gardée sur l'élément et réattachée par une boucle `setInterval` (120 à 150 ms), car Gradio peut recréer le DOM.
- Une prop `undefined` est ignorée côté JS.
- **Chaque mise à jour d'un composant HTML renvoie son état complet** (fond + langue ; données + palette + langue). Un composant dans un onglet monté tardivement ne voit que la dernière mise à jour ; `render_children` n'a pas suffi.
- Les traits des guides arrivent par l'événement `input` ; le calcul ne se fait qu'au retour sur l'onglet Aperçu, pour ne pas ramer pendant le tracé.
- La bascule de langue (`basculer`) met à jour une trentaine de composants : en ajoutant un composant traduit, l'ajouter aussi à ses sorties.

**Peinture dans le navigateur**
- Python envoie une fois : un PNG des zones (n° d'îlot = R + G×256), le PNG du trait, les bleus, un index des pixels par zone. Le remplissage se fait ensuite en JS, en moins de 10 ms. Revenir à un aller-retour Python par clic rendrait chaque remplissage lent.

**Vie privée**
- `GRADIO_ANALYTICS_ENABLED=False` et `HF_HUB_DISABLE_TELEMETRY=1` sont posés **avant** `import gradio`, plus `analytics_enabled=False`.
- La police est servie depuis `polices/` (pas de Google Fonts).
- Résultat vérifié : aucune requête vers l'extérieur pendant une session complète. À revérifier après une mise à jour de Gradio.

**Guide intégré**
- Servi par Gradio via `gr.set_static_paths` à l'adresse `/gradio_api/file=…`. Le bouton « Retour à ColorInk » n'apparaît que sous cette adresse ; il ferme l'onglet (ouvert avec `rel="opener"`) ou revient en arrière.

## Limites connues

- Les lanceurs Windows et macOS n'ont pas été testés.
- L'aperçu travaille sur une image réduite, mais l'export recalcule tout en pleine résolution : sur de très grandes images, cela peut prendre du temps et de la mémoire.
- Un trait très pâle ou très irrégulier demande des guides à la main.

## Pistes

- Tester `lancer.bat` et `lancer.command`, par exemple avec GitHub Actions (machines Windows et macOS).
- Une vraie fenêtre d'application (pywebview) ou le mode application de Chrome, au lieu d'un onglet du navigateur.
- Une démo en ligne (Hugging Face Spaces) : pratique, mais les dessins quitteraient alors l'ordinateur de l'utilisateur. À signaler clairement si quelqu'un la met en place.
