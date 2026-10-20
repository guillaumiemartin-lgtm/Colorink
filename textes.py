# ColorInk — Copyright (c) 2026 Martin Guillaumie — licence MIT (voir LICENSE)
"""Textes de l'interface, en français et en anglais.

Pour ajouter une langue : copier le bloc "en", traduire les valeurs, et ajouter
le code de langue à LANGUES. Les clés ne changent jamais.
"""

LANGUES = ["fr", "en"]

TEXTES = {
    "fr": {
        "bouton_langue": "English",
        "sous_titre": "scanne · nettoie · ajoute des calques pour les couleurs",
        "licence": "Logiciel libre sous licence MIT : utilisez-le, modifiez-le, partagez-le.",
        "local": "Tout reste sur votre ordinateur.",
        "guide": "How to · mode d'emploi",
        # fenêtres
        "f_dessin": "Dessin", "f_papier": "Papier", "f_zones": "Zones", "f_export": "Export",
        # onglets
        "o_apercu": "Aperçu", "o_guides": "Guides", "o_couleurs": "Couleurs",
        # papier
        "eclairage": "Corriger l'éclairage (photo, ombre, dégradé)",
        "balance": "Balance papier / encre",
        "balance_info": "Plus haut : enlève le gris du papier. Plus bas : garde les traits fins.",
        # zones
        "trous": "Fermeture des trous (px)",
        "trous_info": "0 : trait bien fermé · 3-6 : feutre · 10-20 : pinceau sec, photo floue.",
        "seuil": "Sensibilité du trait",
        "seuil_info": "Plus bas : les traits pâles comptent aussi comme limites.",
        # aperçu
        "vue_les_deux": "Aplats + trait", "vue_aplats": "Aplats seuls", "vue_trait": "Trait seul",
        "montrer": "Afficher les guides",
        "depart": "Déposez un dessin pour commencer.",
        "note_zones": "**{n} zones détectées.** Une zone restée en damier a « fui » vers "
                      "l'extérieur : augmentez la fermeture des trous, ou fermez-la avec un guide rouge.",
        "note_guides": "Rouge = limite ajoutée, vert = limite ignorée, violet = zone exclue. "
                       "Ils n'apparaissent pas dans le PSD.",
        "note_reduit": "_Aperçu réduit ({w}×{h}) ; l'export se fait en pleine résolution._",
        # guides
        "aide_guides": "**Fermer** (rouge) : sépare deux zones (finir un cou, une manche…).  \n"
                       "**Ouvrir** (vert) : réunit deux zones (un pouce presque collé à la main…).  \n"
                       "**Exclure** (violet) : entourez une zone d'un trait fermé ; tout le dessin à "
                       "l'intérieur est ignoré (le texte d'une bulle…). Entourez à l'intérieur du "
                       "bord, pas dessus.  \n"
                       "**Gomme** : efface les traits d'aide. **Lissage** : adoucit le trait à main "
                       "levée. Ctrl+Z annule. Ces traits n'apparaissent pas dans le résultat. "
                       "Tracez tout, puis revenez sur **Aperçu** : le calcul se fait à ce moment-là.",
        # couleurs
        "aide_couleurs": "Choisissez une couleur, puis **cliquez sur une zone** pour la remplir. "
                         "Les zones non peintes restent en bleu dans le PSD. Vos couleurs sont "
                         "gardées si vous changez un réglage ou un guide.",
        "couleur": "Couleur",
        "palette": "Palette",
        "palette_complete": "Complète (40 couleurs)",
        "palette_simple": "Simple (14 couleurs)",
        "importer_palette": "Importer une palette Krita / GIMP (.gpl)",
        "annuler": "Annuler", "tout_effacer": "Tout effacer",
        "peint": "{k} zone(s) peinte(s).",
        "clic_exterieur": "Ce clic est en dehors des zones (fond extérieur) : rien à remplir.",
        "clic_sans_dessin": "Déposez d'abord un dessin.",
        "palette_vide": "Aucune couleur trouvée dans ce fichier.",
        "palette_ok": "Palette importée : {k} couleurs.",
        # export
        "par_ilot": "Un calque par îlot",
        "par_ilot_info": "Chaque zone sur son propre calque, rangés dans un groupe Aplats.",
        "creer": "Créer le PSD et l'image finie",
        "telecharger_psd": "Télécharger le PSD", "telecharger_png": "Télécharger l'image finie (PNG)",
        "aucun_dessin": "Aucun dessin chargé.",
        "pret": "Prêt : {n} zones · calques {calques}.",
        "pret_calques": "Trait / groupe Aplats de {n} calques / Papier",
        "pret_simple": "Trait / Aplats / Papier",
    },
    "en": {
        "bouton_langue": "Français",
        "sous_titre": "scan · clean · add layers for colours",
        "licence": "Free software under the MIT licence: use it, change it, share it.",
        "local": "Everything stays on your computer.",
        "guide": "How to · user guide",
        "f_dessin": "Drawing", "f_papier": "Paper", "f_zones": "Zones", "f_export": "Export",
        "o_apercu": "Preview", "o_guides": "Guides", "o_couleurs": "Colours",
        "eclairage": "Correct the lighting (photo, shadow, gradient)",
        "balance": "Paper / ink balance",
        "balance_info": "Higher: removes grey paper. Lower: keeps thin lines.",
        "trous": "Gap closing (px)",
        "trous_info": "0: fully closed lines · 3-6: felt pen · 10-20: dry brush, blurry photo.",
        "seuil": "Line sensitivity",
        "seuil_info": "Lower: faint lines also count as boundaries.",
        "vue_les_deux": "Flats + lines", "vue_aplats": "Flats only", "vue_trait": "Lines only",
        "montrer": "Show guides",
        "depart": "Drop a drawing to start.",
        "note_zones": "**{n} zones found.** A zone left as a checkerboard has \"leaked\" outside: "
                      "increase gap closing, or close it with a red guide.",
        "note_guides": "Red = added boundary, green = ignored boundary, purple = excluded area. "
                       "They do not appear in the PSD.",
        "note_reduit": "_Reduced preview ({w}×{h}); export is done at full resolution._",
        "aide_guides": "**Close** (red): splits two zones (finish a neck, a sleeve…).  \n"
                       "**Open** (green): merges two zones (a thumb almost touching the hand…).  \n"
                       "**Exclude** (purple): circle an area with a closed stroke; all the drawing "
                       "inside is ignored (the text in a speech bubble…). Circle inside the edge, "
                       "not on it.  \n"
                       "**Eraser**: erases helper strokes. **Smoothing**: softens freehand strokes. "
                       "Ctrl+Z undoes. These strokes do not appear in the result. Draw them all, "
                       "then go back to **Preview**: the computation happens then.",
        "aide_couleurs": "Pick a colour, then **click a zone** to fill it. Unpainted zones stay "
                         "blue in the PSD. Your colours are kept if you change a setting or a guide.",
        "couleur": "Colour",
        "palette": "Palette",
        "palette_complete": "Full (40 colours)",
        "palette_simple": "Simple (14 colours)",
        "importer_palette": "Import a Krita / GIMP palette (.gpl)",
        "annuler": "Undo", "tout_effacer": "Clear all",
        "peint": "{k} zone(s) painted.",
        "clic_exterieur": "This click is outside the zones (background): nothing to fill.",
        "clic_sans_dessin": "Drop a drawing first.",
        "palette_vide": "No colour found in this file.",
        "palette_ok": "Palette imported: {k} colours.",
        "par_ilot": "One layer per island",
        "par_ilot_info": "Each zone on its own layer, inside a Flats group.",
        "creer": "Create the PSD and the final image",
        "telecharger_psd": "Download the PSD", "telecharger_png": "Download the final image (PNG)",
        "aucun_dessin": "No drawing loaded.",
        "pret": "Ready: {n} zones · layers {calques}.",
        "pret_calques": "Line art / Flats group of {n} layers / Paper",
        "pret_simple": "Line art / Flats / Paper",
    },
}


def t(langue, cle, **valeurs):
    """Texte traduit ; retombe sur le français si une clé manque."""
    texte = TEXTES.get(langue, TEXTES["fr"]).get(cle) or TEXTES["fr"][cle]
    return texte.format(**valeurs) if valeurs else texte
