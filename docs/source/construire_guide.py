#!/usr/bin/env python3
# ColorInk — Copyright (c) 2026 Martin Guillaumie — licence MIT (voir LICENSE)
"""Reconstruit docs/guide.html (le mode d'emploi) à partir du modèle et des images.

La page finale est autonome : toutes les images y sont intégrées, elle s'ouvre
sans connexion (sauf la police Outfit, remplacée par la police système hors ligne).

    python docs/source/construire_guide.py
"""
import base64
import json
from pathlib import Path

ICI = Path(__file__).parent
IMAGES = ICI / "images"
APPLI = ICI.parent.parent / "images"
POLICES = ICI.parent.parent / "polices"


def data_url(chemin):
    mime = "image/png" if chemin.suffix == ".png" else "image/jpeg"
    return f"data:{mime};base64," + base64.b64encode(chemin.read_bytes()).decode("ascii")


def polices_integrees():
    """@font-face de la police Outfit, intégrée en data URL : aucune connexion extérieure."""
    regles = []
    for graisse in (400, 600, 700, 800):
        f = POLICES / f"outfit-latin-{graisse}-normal.woff2"
        src = "data:font/woff2;base64," + base64.b64encode(f.read_bytes()).decode("ascii")
        regles.append(f"@font-face{{font-family:'Outfit';font-weight:{graisse};font-style:normal;"
                      f"font-display:swap;src:url({src}) format('woff2')}}")
    return "\n".join(regles)


def construire_page():
    """Le contenu de la page, images et police intégrées (sans en-tête HTML)."""
    modele = (ICI / "modele_guide.html").read_text(encoding="utf-8")
    comparateur = {
        dessin: {etape: data_url(IMAGES / f"{prefixe}_{etape}.jpg") for etape in ("photo", "aplats", "peaufine")}
        for dessin, prefixe in (("pyramide", "pyr"), ("logo", "logo"))
    }
    remplacements = {
        "__IMAGES__": json.dumps(comparateur),
        "__LOGO__": data_url(APPLI / "logo.png"),
        "__ICONE__": data_url(APPLI / "icone.png"),
        "__CAP_APERCU__": data_url(IMAGES / "cap_apercu.jpg"),
        "__CAP_GUIDES__": data_url(IMAGES / "cap_guides.jpg"),
        "__CAP_COULEURS__": data_url(IMAGES / "cap_couleurs.jpg"),
        "__GUIDE_AVANT_APRES__": data_url(IMAGES / "guide_avant_apres.jpg"),
        "__POLICES__": polices_integrees(),
    }
    page = modele
    for cle, valeur in remplacements.items():
        page = page.replace(cle, valeur)
    return page


def main():
    page = construire_page()
    sortie = ICI.parent / "guide.html"
    # le modèle n'a pas d'en-tête HTML complet (il est aussi publié tel quel) : on l'ajoute
    entete = ('<!doctype html>\n<html lang="fr" data-lg="fr">\n<head>\n<meta charset="utf-8">\n'
              '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
              '<style>body{margin:0}img{max-width:100%}</style>\n</head>\n<body>\n')
    sortie.write_text(entete + page + "\n</body>\n</html>\n", encoding="utf-8")
    print(f"{sortie} ({sortie.stat().st_size // 1024} Ko)")


if __name__ == "__main__":
    main()
