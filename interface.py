#!/usr/bin/env python3
# ColorInk — préparation d'un dessin à l'encre pour la mise en couleur
# Copyright (c) 2026 Martin Guillaumie — licence MIT (voir LICENSE)
"""Interface visuelle de ColorInk — s'ouvre dans le navigateur, tout reste en local.

Lancer :  python interface.py   (ou les lanceurs lancer.sh / lancer.bat / lancer.command)
"""
import os

# Aucune connexion extérieure : Gradio envoie par défaut des statistiques d'usage
# (api.gradio.app, huggingface.co). À régler avant d'importer gradio.
os.environ["GRADIO_ANALYTICS_ENABLED"] = "False"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"

import base64
import json
import re
import tempfile
import urllib.parse
from functools import lru_cache
from pathlib import Path

import cv2
import gradio as gr
import numpy as np

from colorink import (COULEUR_EXCLUSION, COULEUR_GUIDE, COULEUR_PASSAGE, PALETTE_DEFAUT, PALETTES, calculer,
                      charger, enregistrer, enregistrer_png, fusion, lire_gpl, zone_entouree)
from textes import t

DOSSIER_TMP = Path(tempfile.mkdtemp(prefix="colorink_"))
APERCU_MAX = 1400  # px : l'aperçu est calculé en réduit pour rester fluide
GUIDES_MAX = 1600  # px : taille du dessin dans l'onglet Guides
# Éditeur de guides sur mesure (toile, outils, lissage) : voir editeur_guides.js
JS_GUIDES = (Path(__file__).parent / "editeur_guides.js").read_text(encoding="utf-8")
DOSSIER_IMAGES = Path(__file__).parent / "images"
# Mode d'emploi (docs/guide.html, page autonome) servi par l'application elle-même
GUIDE = (Path(__file__).parent / "docs" / "guide.html").resolve()
DOSSIER_POLICES = (Path(__file__).parent / "polices").resolve()
gr.set_static_paths(paths=[GUIDE.parent, DOSSIER_POLICES])
URL_GUIDE = "/gradio_api/file=" + urllib.parse.quote(str(GUIDE))
LOGO = "data:image/png;base64," + base64.b64encode((DOSSIER_IMAGES / "logo.png").read_bytes()).decode("ascii")
# Pot de peinture côté navigateur (remplissage instantané) : voir peinture.js
JS_PEINTURE = (Path(__file__).parent / "peinture.js").read_text(encoding="utf-8")


# ---------------------------------------------------------------- outils d'image

def damier(h, w, s=12):
    y, x = np.mgrid[:h, :w]
    c = np.where(((x // s) + (y // s)) % 2, 215, 245).astype(np.uint8)
    return np.dstack([c, c, c, np.full_like(c, 255)])


def reduire(rgb, taille_max=APERCU_MAX):
    h, w = rgb.shape[:2]
    f = min(1.0, taille_max / max(h, w))
    if f == 1.0:
        return rgb, 1.0
    return cv2.resize(rgb, (int(w * f), int(h * f)), interpolation=cv2.INTER_AREA), f


@lru_cache(maxsize=4)
def _charger_cache(chemin):
    return charger(chemin)


def charger_vite(chemin):
    """Évite de relire la photo à chaque mouvement de curseur."""
    return _charger_cache(chemin).copy()


def hex_vers_rgb(c):
    """« #rrggbb », « #rgb » ou « rgb(a)(r, g, b…) » → (r, g, b)."""
    c = (c or "").strip()
    m = re.match(r"rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)", c)
    if m:
        return tuple(int(round(float(v))) for v in m.groups())
    c = c.lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    try:
        return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return (231, 76, 60)


# ---------------------------------------------------------------- guides et passages

def lire_traits(valeur):
    """Data URL PNG envoyée par l'éditeur de guides → image RVBA, ou None."""
    if not valeur or "," not in valeur:
        return None
    try:
        data = np.frombuffer(base64.b64decode(valeur.split(",", 1)[1]), np.uint8)
        img = cv2.imdecode(data, cv2.IMREAD_UNCHANGED)
    except (ValueError, cv2.error):
        return None
    if img is None or img.ndim != 3 or img.shape[2] != 4:
        return None
    return cv2.cvtColor(img, cv2.COLOR_BGRA2RGBA)


def masques_aides(valeur, h, w):
    """Traits de l'onglet Guides → (guides, passages, exclusions), masques h×w ou None.

    Chaque pixel tracé est rangé selon la couleur d'outil la plus proche
    (rouge, vert ou violet) ; la gomme a déjà effacé ce qu'elle a touché. Le contour
    violet est rempli : toute la zone entourée est exclue du découpage.
    """
    c = lire_traits(valeur)
    if c is None:
        return None, None, None
    trace = c[..., 3] > 40  # ignore le très léger halo d'anticrénelage
    if not trace.any():
        return None, None, None
    refs = np.array([COULEUR_GUIDE, COULEUR_PASSAGE, COULEUR_EXCLUSION], np.int32)
    proche = ((c[..., None, :3].astype(np.int32) - refs[None, None]) ** 2).sum(-1).argmin(-1)
    guides, passages, contours = ((trace & (proche == k)) for k in range(3))

    def ajuster(m):
        if m is None or not m.any():
            return None
        if m.shape != (h, w):
            m = cv2.resize(m.astype(np.uint8), (w, h), interpolation=cv2.INTER_NEAREST) > 0
        return m
    exclusions = zone_entouree(contours) if contours.any() else None
    return ajuster(guides), ajuster(passages), ajuster(exclusions)


def reduire_masque(m, w, h):
    if m is None or m.shape == (h, w):
        return m
    return cv2.resize(m.astype(np.uint8) * 255, (w, h), interpolation=cv2.INTER_AREA) > 0


def fond_guides(chemin):
    """Le scan, réduit et en JPEG data URL, sert de fond à l'éditeur de guides.

    Les guides sont agrandis à la taille réelle du dessin au moment du calcul.
    """
    if not chemin:
        return ""
    petit, _ = reduire(charger_vite(chemin), GUIDES_MAX)
    ok, buf = cv2.imencode(".jpg", cv2.cvtColor(petit, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 88])
    return "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode("ascii")


# ---------------------------------------------------------------- aperçu

def composer(etat, peintures, vue, montrer):
    """Image de l'onglet Aperçu, à partir du dernier calcul (rapide : pas de recalcul)."""
    res = etat["res"]
    aplat = res.aplats(peintures)
    h, w = aplat.shape[:2]
    fond = damier(h, w)
    if vue == "trait":
        img = fusion(fond, res.trait)
    elif vue == "aplats":
        img = fusion(fond, aplat)
    else:
        img = fusion(fusion(fond, aplat), res.trait)
    if montrer:  # aides visibles dans l'aperçu seulement
        for m, coul, force in ((etat["exclusions"], COULEUR_EXCLUSION, 0.35),
                               (etat["guides"], COULEUR_GUIDE, 0.65), (etat["passages"], COULEUR_PASSAGE, 0.65)):
            if m is not None:
                img[m] = (img[m] * (1 - force) + np.array([*coul, 255]) * force).astype(np.uint8)
    return img[..., :3]


def png_data_url(img):
    ok, buf = cv2.imencode(".png", img)
    return "data:image/png;base64," + base64.b64encode(buf.tobytes()).decode("ascii")


def donnees_couleurs(etat, chemin):
    """Tout ce dont le pot de peinture du navigateur a besoin, envoyé une fois par calcul.

    zones : numéro d'îlot codé dans les canaux R et G d'un PNG (jusqu'à 65 535 îlots) ;
    trait : le calque Trait en PNG ; bleus : couleur de départ de chaque îlot.
    """
    if etat is None:
        return ""
    res = etat["res"]
    h, w = res.lab.shape
    lab = res.lab.astype(np.uint32)
    code = np.dstack([np.zeros((h, w), np.uint8), ((lab >> 8) & 255).astype(np.uint8),
                      (lab & 255).astype(np.uint8)])  # ordre BGR pour OpenCV : R = octet bas
    trait = cv2.cvtColor(res.trait, cv2.COLOR_RGBA2BGRA)
    return json.dumps({"id": str(chemin), "w": w, "h": h, "zones": png_data_url(code),
                       "trait": png_data_url(trait), "bleus": res.palette.tolist()})


def lire_peintures(valeur):
    """Liste des clics envoyée par le navigateur → [(x, y, (r, g, b)), …]."""
    try:
        clics = json.loads(valeur) if valeur else []
        return [(float(x), float(y), hex_vers_rgb(c)) for x, y, c in clics]
    except (ValueError, TypeError):
        return []


def note(etat, langue):
    if etat is None:
        return t(langue, "depart")
    txt = t(langue, "note_zones", n=etat["res"].n)
    if any(etat[k] is not None for k in ("guides", "passages", "exclusions")):
        txt += "  \n" + t(langue, "note_guides")
    if etat["f"] < 1:
        h, w = etat["res"].lab.shape
        txt += "  \n" + t(langue, "note_reduit", w=w, h=h)
    return txt


def apercu(chemin, editeur, trous, seuil, vue, eclairage, balance, montrer, peintures, langue, palette):
    """Recalcule les zones (en réduit) ; renvoie aperçu, note, état, image Couleurs."""
    if not chemin:
        return None, t(langue, "depart"), None, gr.HTML(donnees="", palette=palette, langue=langue), ""
    rgb = charger_vite(chemin)
    guides, passages, exclusions = masques_aides(editeur, *rgb.shape[:2])
    petit, f = reduire(rgb)
    h, w = petit.shape[:2]
    guides, passages, exclusions = (reduire_masque(m, w, h) for m in (guides, passages, exclusions))
    t_px = max(0, round(trous * f))  # même effet visuel qu'en pleine taille
    res = calculer(petit, t_px, seuil, eclairage, balance, guides, passages, exclusions)
    etat = {"res": res, "guides": guides, "passages": passages, "exclusions": exclusions, "f": f}
    d = donnees_couleurs(etat, chemin)
    return (composer(etat, peintures, vue, montrer), note(etat, langue), etat,
            gr.HTML(donnees=d, palette=palette, langue=langue), d)


def reafficher(etat, peintures, vue, montrer, langue):
    """Changement de vue ou d'affichage des guides : pas besoin de recalculer."""
    if etat is None:
        return None, t(langue, "depart")
    return composer(etat, peintures, vue, montrer), note(etat, langue)


# ---------------------------------------------------------------- couleurs

def choix_palettes(langue, importees):
    """Entrées du menu « Palette » : palettes intégrées puis palettes importées."""
    return ([(t(langue, f"palette_{cle}"), cle) for cle in PALETTES]
            + [(cle.split(":", 1)[1], cle) for cle in importees])


def changer_palette(cle, importees, langue, donnees):
    pal = json.dumps(list(PALETTES.get(cle) or importees.get(cle) or PALETTE_DEFAUT))
    return pal, gr.HTML(palette=pal, langue=langue, donnees=donnees)


def importer_palette(fichier, importees, langue):
    """Ajoute une palette .gpl au menu et la sélectionne."""
    if not fichier:
        return importees, gr.update(), ""
    couleurs = lire_gpl(fichier)
    if not couleurs:
        return importees, gr.update(), t(langue, "palette_vide")
    cle = "gpl:" + Path(fichier).stem
    importees = {**importees, cle: couleurs}
    return (importees, gr.update(choices=choix_palettes(langue, importees), value=cle),
            t(langue, "palette_ok", k=len(couleurs)))


# ---------------------------------------------------------------- export

def exporter(chemin, editeur, trous, seuil, eclairage, balance, par_ilot, peintures, langue):
    if not chemin:
        raise gr.Error(t(langue, "aucun_dessin"))
    rgb = charger(chemin)
    guides, passages, exclusions = masques_aides(editeur, *rgb.shape[:2])
    res = calculer(rgb, int(trous), seuil, eclairage, balance, guides, passages, exclusions)
    base = Path(chemin).stem
    psd = DOSSIER_TMP / f"{base}_colorink.psd"
    png = DOSSIER_TMP / f"{base}_colorink.png"
    enregistrer(psd, res, peintures, guides, passages, un_calque_par_ilot=par_ilot, langue=langue,
                exclusions=exclusions)
    enregistrer_png(png, res, peintures)
    calques = t(langue, "pret_calques", n=res.n) if par_ilot else t(langue, "pret_simple")
    return (gr.update(value=str(psd), visible=True), gr.update(value=str(png), visible=True),
            t(langue, "pret", n=res.n, calques=calques))


# ---------------------------------------------------------------- apparence (style « fenêtres »)

ACCENT = "#ef4444"        # couleur de l'interface (bordures, titres, boutons)
ACCENT_PALE = "#fde8e8"   # survol, fonds légers
ACCENT_FONCE = "#b91c1c"  # ombre des boutons sur fond rouge

THEME = gr.themes.Base(
    font=["Outfit", "system-ui", "sans-serif"],   # police fournie avec l'appli (dossier polices/)
    radius_size=gr.themes.sizes.radius_none,
).set(
    body_background_fill="#ffffff",
    body_text_color=ACCENT,
    body_text_color_subdued="#ef4444b0",
    block_background_fill="#ffffff",
    block_border_color=ACCENT,
    block_border_width="2px",
    block_label_background_fill=ACCENT,
    block_label_text_color="#ffffff",
    block_label_border_color=ACCENT,
    block_title_text_color=ACCENT,
    block_info_text_color="#ef4444b0",
    block_shadow="none",
    border_color_primary=ACCENT,
    border_color_accent=ACCENT,
    input_background_fill="#ffffff",
    input_border_color=ACCENT,
    input_border_width="2px",
    slider_color=ACCENT,
    checkbox_background_color_selected=ACCENT,
    checkbox_border_color=ACCENT,
    checkbox_border_color_selected=ACCENT,
    checkbox_label_background_fill="#ffffff",
    checkbox_label_background_fill_selected=ACCENT,
    checkbox_label_text_color_selected="#ffffff",
    checkbox_label_border_color=ACCENT,
    checkbox_label_border_width="2px",
    button_primary_background_fill=ACCENT,
    button_primary_background_fill_hover="#ffffff",
    button_primary_text_color="#ffffff",
    button_primary_text_color_hover=ACCENT,
    button_primary_border_color=ACCENT,
    button_primary_border_color_hover=ACCENT,
    button_secondary_border_color_hover=ACCENT,
    input_border_color_focus=ACCENT,
    button_secondary_background_fill="#ffffff",
    button_secondary_background_fill_hover=ACCENT,
    button_secondary_text_color=ACCENT,
    button_secondary_text_color_hover="#ffffff",
    button_secondary_border_color=ACCENT,
    button_border_width="2px",
    color_accent_soft=ACCENT_PALE,
)

POLICE_LOCALE = "".join(
    f"@font-face {{ font-family: 'Outfit'; font-weight: {g}; font-style: normal; font-display: swap; "
    f"src: url('/gradio_api/file={urllib.parse.quote(str(DOSSIER_POLICES / f'outfit-latin-{g}-normal.woff2'))}') format('woff2'); }}\n"
    for g in (400, 600, 700, 800))

CSS = POLICE_LOCALE + """
:root { --bleu: #ef4444; }   /* nom historique de la variable : couleur d'accent */
body, gradio-app, .gradio-container { background: #fff !important; }
.gradio-container { max-width: 1800px !important; padding: 24px !important; }
footer { display: none !important; }
/* fenêtres façon Mac rétro */
.fenetre {
  background: #fff !important; border: 2px solid var(--bleu) !important;
  box-shadow: 4px 4px 0 var(--bleu) !important; padding: 0 !important; gap: 0 !important;
}
.titre {
  background: var(--bleu); color: #fff !important; padding: 7px 12px !important;
  margin: 0 !important; border: 0 !important;
}
.titre * { color: #fff !important; margin: 0 !important; }
.titre h1 { font-size: 17px; font-weight: 700; }
.titre p { font-size: 12px; text-transform: uppercase; letter-spacing: .06em; font-weight: 700; }
.corps { padding: 12px !important; gap: 12px !important; background: #fff; }
.corps .block, .fenetre .block { box-shadow: none !important; }
.sans-bord, .sans-bord .block { border: 0 !important; }
button.primary, button.secondary { font-weight: 700 !important; box-shadow: 3px 3px 0 var(--bleu); }
button.primary:active, button.secondary:active { box-shadow: none; transform: translate(3px, 3px); }
button.primary { background: var(--bleu) !important; color: #fff !important; }
button.primary:hover { background: #fff !important; color: var(--bleu) !important; }
.icon-button-wrapper, .icon-button-wrapper button, .icon-buttons button {
  background: #fff !important; color: var(--bleu) !important; border-color: var(--bleu) !important; }
.icon-button-wrapper svg, .icon-buttons svg, .image-container svg { color: var(--bleu) !important; stroke: currentColor; }
.onglets button[role=tab] { color: var(--bleu) !important; font-weight: 700; text-transform: uppercase;
  letter-spacing: .06em; font-size: 12px; border: 0 !important; }
.onglets button[role=tab][aria-selected=true] { background: var(--bleu) !important; color: #fff !important; }
.onglets .tab-wrapper, .onglets [role=tablist] { border-bottom: 2px solid var(--bleu) !important; }
.entete { align-items: center !important; background: var(--bleu) !important; padding-right: 12px !important; }
.entete .titre { flex: 1; }
.langue { box-shadow: 3px 3px 0 #b91c1c !important; border-color: #fff !important; }
.cliquable img { cursor: crosshair !important; }
.colonne-droite { gap: 24px !important; }
/* onglet actif : barre jaune (jaune du panneau du logo) */
.onglets button[role=tab]::after { background: #fcdc1c !important; height: 4px !important; }
.onglets button[role=tab]:hover:not([aria-selected=true]) { background: var(--bleu) !important; color: #fff !important; }
/* survol des choix (Aplats + trait, etc.) : fond rouge, texte blanc */
label:has(input[type=radio]):hover, label:has(input[type=radio]):hover *,
label:has(input[type=checkbox]):hover, label:has(input[type=checkbox]):hover span { color: #fff !important; }
label:has(input[type=checkbox]):hover { background: var(--bleu) !important; }
button:focus-visible, button:focus { outline-color: var(--bleu) !important; }
button.primary:focus, button.primary:active { border-color: var(--bleu) !important; }
.bloc-signature { padding: 8px 4px !important; }
.signature { text-align: center; color: var(--bleu); font-size: 12px; line-height: 1.5; }
.bouton-guide { display: block; margin: 0 0 22px; padding: 10px 14px; background: #fcdc1c; color: var(--bleu) !important;
  border: 2px solid var(--bleu); box-shadow: 4px 4px 0 var(--bleu); font-weight: 800; font-size: 15px;
  text-decoration: none !important; letter-spacing: .02em; }
.bouton-guide:hover { background: var(--bleu); color: #fff !important; }
.bouton-guide:active { transform: translate(3px, 3px); box-shadow: 1px 1px 0 var(--bleu); }
.signature img { width: 82%; max-width: 280px; display: block; margin: 0 auto 12px; }
.signature p { margin: 0 !important; }
.signature .discret { opacity: .75; font-size: 11px; }
.note p, .note em { font-size: 12px; color: var(--bleu); }
input[type=range] { accent-color: var(--bleu); }
.apercu img { image-rendering: auto; }
"""


def bloc_signature(lg):
    """Bouton du mode d'emploi, logo dessiné, puis licence et signature (colonne de droite)."""
    return (f'<div class="signature">'
            f'<a class="bouton-guide" href="{URL_GUIDE}#{lg}" target="_blank" rel="opener">{t(lg, "guide")}</a>'
            f'<img src="{LOGO}" alt="ColorInk">'
            f'<p><b>ColorInk</b> · © 2026 Martin Guillaumie</p>'
            f'<p>{t(lg, "licence")}</p><p class="discret">{t(lg, "local")}</p></div>')


def libelles_vue(lg):
    return [(t(lg, "vue_les_deux"), "les_deux"), (t(lg, "vue_aplats"), "aplats"), (t(lg, "vue_trait"), "trait")]


def construire(lg="fr"):
    with gr.Blocks(title="ColorInk", analytics_enabled=False) as app:
        langue = gr.State(lg)
        etat = gr.State(None)        # dernier calcul de l'aperçu (en réduit)
        peintures = gr.State([])     # clics de pot de peinture : (x, y relatifs, couleur)
        # Les composants sur mesure (guides, peinture) peuvent n'être créés qu'à la première
        # ouverture de leur onglet, et ne voir alors que la dernière mise à jour : chaque
        # mise à jour leur renvoie donc tout leur état, mémorisé ici.
        palette = gr.State(json.dumps(PALETTE_DEFAUT))  # palette affichée par le pot de peinture
        fond = gr.State("")          # fond de l'éditeur de guides
        donnees = gr.State("")       # zones + trait envoyés au pot de peinture
        importees = gr.State({})     # palettes .gpl importées : « gpl:nom » → couleurs

        with gr.Row(elem_classes="fenetre entete", equal_height=True):
            titre = gr.Markdown(f"# ColorInk\n{t(lg, 'sous_titre')}", elem_classes="titre")
            bouton_langue = gr.Button(t(lg, "bouton_langue"), variant="secondary", scale=0,
                                      min_width=110, elem_classes="langue")

        with gr.Row(equal_height=False):
            # ------------------------------------------------ réglages
            with gr.Column(scale=5, min_width=280, elem_classes="fenetre"):
                f_dessin = gr.Markdown(t(lg, "f_dessin"), elem_classes="titre")
                with gr.Column(elem_classes="corps"):
                    entree = gr.Image(type="filepath", show_label=False,
                                      sources=["upload", "clipboard"], height=260)
                f_papier = gr.Markdown(t(lg, "f_papier"), elem_classes="titre")
                with gr.Column(elem_classes="corps"):
                    eclairage = gr.Checkbox(value=True, label=t(lg, "eclairage"))
                    balance = gr.Slider(0, 0.6, value=0.15, step=0.05, label=t(lg, "balance"),
                                        info=t(lg, "balance_info"))
                f_zones = gr.Markdown(t(lg, "f_zones"), elem_classes="titre")
                with gr.Column(elem_classes="corps"):
                    trous = gr.Slider(0, 20, value=3, step=1, label=t(lg, "trous"), info=t(lg, "trous_info"))
                    seuil = gr.Slider(0.1, 0.8, value=0.35, step=0.05, label=t(lg, "seuil"),
                                      info=t(lg, "seuil_info"))

            # ------------------------------------------------ onglets (colonne centrale)
            with gr.Column(scale=10, min_width=480, elem_classes="fenetre"):
                with gr.Tabs(elem_classes="onglets"):
                    with gr.Tab(t(lg, "o_apercu")) as onglet_apercu:
                        with gr.Column(elem_classes="corps"):
                            with gr.Row(equal_height=True):
                                vue = gr.Radio(libelles_vue(lg), value="les_deux", show_label=False,
                                               container=False, scale=3)
                                montrer = gr.Checkbox(value=True, label=t(lg, "montrer"),
                                                      container=False, scale=1)
                            sortie = gr.Image(show_label=False, interactive=False, height=640,
                                              elem_classes="apercu sans-bord")
                            info_apercu = gr.Markdown(t(lg, "depart"), elem_classes="note")

                    # render_children : les onglets sont créés dès le départ (cachés), pour que
                    # les composants sur mesure reçoivent toutes les mises à jour
                    with gr.Tab(t(lg, "o_guides"), render_children=True) as onglet_guides:
                        with gr.Column(elem_classes="corps"):
                            aide_guides = gr.Markdown(t(lg, "aide_guides"), elem_classes="note")
                            editeur = gr.HTML(value="", html_template="", js_on_load=JS_GUIDES,
                                              fond="", langue=lg, elem_classes="sans-bord")

                    with gr.Tab(t(lg, "o_couleurs"), render_children=True) as onglet_couleurs:
                        with gr.Column(elem_classes="corps"):
                            aide_couleurs = gr.Markdown(t(lg, "aide_couleurs"), elem_classes="note")
                            with gr.Row(equal_height=True):
                                choix_palette = gr.Dropdown(choix_palettes(lg, {}), value="complete",
                                                            label=t(lg, "palette"), interactive=True, scale=2)
                                importer = gr.UploadButton(t(lg, "importer_palette"), file_types=[".gpl"],
                                                           type="filepath", variant="secondary", size="sm",
                                                           scale=1)
                            peinture = gr.HTML(value="", html_template="", js_on_load=JS_PEINTURE,
                                               donnees="", palette=json.dumps(PALETTE_DEFAUT), langue=lg,
                                               elem_classes="sans-bord")
                            info_couleurs = gr.Markdown("", elem_classes="note")

            # ------------------------------------------------ export, logo et signature
            with gr.Column(scale=4, min_width=240, elem_classes="colonne-droite"):
                with gr.Column(elem_classes="fenetre"):
                    f_export = gr.Markdown(t(lg, "f_export"), elem_classes="titre")
                    with gr.Column(elem_classes="corps"):
                        par_ilot = gr.Checkbox(value=False, label=t(lg, "par_ilot"),
                                               info=t(lg, "par_ilot_info"))
                        bouton = gr.Button(t(lg, "creer"), variant="primary")
                        fichier_psd = gr.DownloadButton(t(lg, "telecharger_psd"), variant="secondary",
                                                        visible=False)
                        fichier_png = gr.DownloadButton(t(lg, "telecharger_png"), variant="secondary",
                                                        visible=False)
                        statut = gr.Markdown(elem_classes="note")
                signature = gr.HTML(bloc_signature(lg), js_on_load=None, elem_classes="bloc-signature")

        # ------------------------------------------------ événements
        reglages = [entree, editeur, trous, seuil, vue, eclairage, balance, montrer, peintures, langue, palette]
        sorties_calcul = [sortie, info_apercu, etat, peinture, donnees]

        def nouveau_dessin(chemin, lg):
            f = fond_guides(chemin)
            return (gr.HTML(value="", fond=f, langue=lg), f, [], gr.update(visible=False),
                    gr.update(visible=False), "")
        entree.change(nouveau_dessin, [entree, langue],
                      [editeur, fond, peintures, fichier_psd, fichier_png, statut]) \
              .then(apercu, reglages, sorties_calcul)
        eclairage.change(apercu, reglages, sorties_calcul)
        for c in (trous, seuil, balance):
            c.release(apercu, reglages, sorties_calcul)
        # les guides se tracent sans calcul ; l'aperçu se met à jour en revenant sur son onglet
        onglet_apercu.select(apercu, reglages, sorties_calcul)
        onglet_couleurs.select(apercu, reglages, sorties_calcul)
        for c in (vue, montrer):
            c.change(reafficher, [etat, peintures, vue, montrer, langue], [sortie, info_apercu])

        # le pot de peinture travaille dans le navigateur ; Python ne reçoit que les clics
        peinture.change(lire_peintures, peinture, peintures)
        choix_palette.change(changer_palette, [choix_palette, importees, langue, donnees], [palette, peinture])
        importer.upload(importer_palette, [importer, importees, langue], [importees, choix_palette, info_couleurs])

        bouton.click(exporter, [entree, editeur, trous, seuil, eclairage, balance, par_ilot, peintures, langue],
                     [fichier_psd, fichier_png, statut])

        # ------------------------------------------------ changement de langue
        cibles = [langue, titre, bouton_langue, f_dessin, f_papier, f_zones, f_export,
                  eclairage, balance, trous, seuil, par_ilot, bouton, fichier_psd, fichier_png,
                  onglet_apercu, onglet_guides, onglet_couleurs, vue, montrer, info_apercu,
                  editeur, aide_guides, aide_couleurs, peinture, importer, signature, statut,
                  info_couleurs, choix_palette]

        def basculer(lg, etat_, importees_, fond_, palette_, donnees_):
            n = "en" if lg == "fr" else "fr"
            return [n,
                    f"# ColorInk\n{t(n, 'sous_titre')}", gr.update(value=t(n, "bouton_langue")),
                    t(n, "f_dessin"), t(n, "f_papier"), t(n, "f_zones"), t(n, "f_export"),
                    gr.update(label=t(n, "eclairage")),
                    gr.update(label=t(n, "balance"), info=t(n, "balance_info")),
                    gr.update(label=t(n, "trous"), info=t(n, "trous_info")),
                    gr.update(label=t(n, "seuil"), info=t(n, "seuil_info")),
                    gr.update(label=t(n, "par_ilot"), info=t(n, "par_ilot_info")),
                    gr.update(value=t(n, "creer")),
                    gr.update(label=t(n, "telecharger_psd")), gr.update(label=t(n, "telecharger_png")),
                    gr.update(label=t(n, "o_apercu")), gr.update(label=t(n, "o_guides")),
                    gr.update(label=t(n, "o_couleurs")),
                    gr.update(choices=libelles_vue(n)), gr.update(label=t(n, "montrer")), note(etat_, n),
                    gr.HTML(langue=n, fond=fond_), t(n, "aide_guides"), t(n, "aide_couleurs"),
                    gr.HTML(langue=n, palette=palette_, donnees=donnees_),
                    gr.update(label=t(n, "importer_palette")),
                    gr.HTML(value=bloc_signature(n)), "", "",
                    gr.update(label=t(n, "palette"), choices=choix_palettes(n, importees_))]
        bouton_langue.click(basculer, [langue, etat, importees, fond, palette, donnees], cibles)
    return app


app = construire("fr")

if __name__ == "__main__":
    app.launch(inbrowser=True, server_name="127.0.0.1", theme=THEME, css=CSS,
               favicon_path=str(DOSSIER_IMAGES / "icone.png"))
