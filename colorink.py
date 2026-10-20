#!/usr/bin/env python3
# ColorInk — préparation d'un dessin à l'encre pour la mise en couleur
# Copyright (c) 2026 Martin Guillaumie — licence MIT (voir LICENSE)
"""colorink.py — cœur de ColorInk (sans interface).

À partir d'un scan ou d'une photo de dessin à l'encre :
  1. le papier est rendu transparent (avec correction de l'éclairage) → calque « Trait »
  2. chaque forme fermée devient un îlot de couleur, étendu sous le trait → « Aplats »
  3. un fond blanc → « Papier »
et le tout est enregistré en PSD (Krita, GIMP, Photopea, Photoshop…).

Ligne de commande :
  python colorink.py dessin.png                 # crée dessin_colorink.psd
  python colorink.py dossier/                   # toutes les images du dossier
  python colorink.py dessin.png --trous 4       # ferme les trous jusqu'à ~4 px
  python colorink.py dessin.png --calques       # un calque par îlot
  python colorink.py dessin.png --en            # noms de calques en anglais
Interface visuelle : python interface.py
"""
import argparse
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from skimage.segmentation import expand_labels

EXTS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}
SUFFIXE = "_colorink"

# Noms des calques selon la langue
NOMS_CALQUES = {
    "fr": {"trait": "Trait", "aplats": "Aplats", "papier": "Papier", "zone": "Zone",
           "guides": "Aide : guides", "passages": "Aide : passages",
           "exclusions": "Aide : zones exclues"},
    "en": {"trait": "Line art", "aplats": "Flats", "papier": "Paper", "zone": "Zone",
           "guides": "Helper: guides", "passages": "Helper: openings",
           "exclusions": "Helper: excluded areas"},
}
COULEUR_GUIDE = (255, 70, 40)     # rouge : « fermer ici »
COULEUR_PASSAGE = (25, 195, 125)  # vert : « ouvrir ici »
COULEUR_EXCLUSION = (142, 68, 173)  # violet : « ignorer tout ce qui est entouré »


# ---------------------------------------------------------------- lecture

def charger(chemin):
    """Image → tableau RVB uint8. Gère les chemins avec accents (Windows)."""
    data = np.fromfile(str(chemin), dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_COLOR) if data.size else None
    if img is None:
        raise ValueError(f"impossible de lire {chemin}")
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)


# ---------------------------------------------------------------- 1. papier → transparence

def fond_papier(f):
    """Estime la couleur du papier en chaque point (éclairage, ombres, dégradés).

    On efface le trait (filtre « maximum » : le clair gagne), puis on lisse.
    """
    h, w = f.shape[:2]
    e = min(1.0, 800 / max(h, w))  # calcul en réduit : rapide et suffisant
    petit = cv2.resize(f, (max(1, int(w * e)), max(1, int(h * e))), interpolation=cv2.INTER_AREA)
    k = max(3, int(max(petit.shape[:2]) * 0.025) | 1)  # plus large que le trait
    noyau = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    fond = cv2.dilate(petit, noyau)
    fond = cv2.erode(fond, noyau)  # recolle aux bords réels de l'ombre
    fond = cv2.GaussianBlur(fond, (0, 0), k / 2)
    return cv2.resize(fond, (w, h), interpolation=cv2.INTER_LINEAR)


def blanc_vers_alpha(rgb, eclairage=True, balance=0.15):
    """Équivalent de « Couleur vers alpha (blanc) », avec correction de l'éclairage.

    balance : 0 = garde toutes les nuances grises, plus haut = le papier
    gris/ombré part davantage, seule l'encre franche reste.
    Retourne un tableau float RVBA (0-1).
    """
    f = rgb.astype(np.float32) / 255.0
    if eclairage:
        papier = fond_papier(f)
    else:  # couleur unique du papier = teinte claire dominante
        gris = f.mean(axis=2)
        papier = np.percentile(f[gris > np.percentile(gris, 60)], 50, axis=0)
    papier = np.clip(papier, 1e-3, 1)
    # alpha = à quel point le pixel s'éloigne du papier vers le noir
    a = np.clip(1.0 - (f / papier).min(axis=2), 0, 1)
    b = float(np.clip(balance, 0, 0.9))
    a = np.clip((a - b) / (1 - b), 0, 1)
    with np.errstate(divide="ignore", invalid="ignore"):
        couleur = (f - papier * (1 - a[..., None])) / a[..., None]
    couleur = np.nan_to_num(np.clip(couleur, 0, 1))
    return np.dstack([couleur, a])


# ---------------------------------------------------------------- 2. zones fermées

def zones(alpha, trous=2, seuil=0.35, aire_min=None, guides=None, passages=None):
    """Étiquette les formes fermées : 0 = extérieur, 1..n = îlots.

    trous    : épaissit le trait de ce rayon (px) pour boucher les petites ouvertures
    guides   : masque booléen ajouté au trait (« fermer ici »)
    passages : masque booléen retiré du trait après épaississement (« ouvrir ici »)
    Les îlots sont ensuite étendus sous le trait pour qu'il n'y ait pas de liseré.
    """
    if aire_min is None:  # ignore les poussières, proportionnellement à la taille
        aire_min = max(12, int(alpha.size * 2e-5))
    trait = alpha > seuil
    if guides is not None:
        trait = trait | guides
    if trous > 0:
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * trous + 1,) * 2)
        trait = cv2.dilate(trait.astype(np.uint8), k) > 0
    if passages is not None:
        trait = trait & ~passages
    n, lab = cv2.connectedComponents((~trait).astype(np.uint8), connectivity=4)

    # extérieur = zones qui touchent le bord de l'image
    bord = np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))
    exterieur = set(bord.tolist()) - {0}

    aires = np.bincount(lab.ravel(), minlength=n)
    garde = np.zeros(n, np.int32)
    k = 1
    for i in range(1, n):
        if i in exterieur:
            garde[i] = -1
        elif aires[i] >= aire_min:
            garde[i] = k
            k += 1
    nouv = garde[lab]
    # étiquette temporaire pour l'extérieur, puis remplissage sous le trait
    tmp = np.where(nouv == -1, k, nouv)
    tmp = expand_labels(tmp, distance=max(alpha.shape))
    tmp[tmp == k] = 0
    return tmp.astype(np.int32), k - 1


# ---------------------------------------------------------------- 3. couleurs des îlots

def nuances_bleues(n):
    """n nuances de bleu toutes différentes (teinte, saturation, luminosité variées)."""
    def halton(i, base):
        f, r = 1.0, 0.0
        while i > 0:
            f /= base
            r += f * (i % base)
            i //= base
        return r
    vus, out, i = set(), [], 1
    while len(out) < n:
        h = 95 + 30 * halton(i, 2)      # 190°–250° (OpenCV : 0–179)
        sat = 70 + 185 * halton(i, 3)
        val = 95 + 160 * halton(i, 5)
        c = tuple(cv2.cvtColor(np.uint8([[[h, sat, val]]]), cv2.COLOR_HSV2RGB)[0, 0].tolist())
        if c not in vus:
            vus.add(c)
            out.append(c)
        i += 1
    return np.array(out, np.uint8)


def palette_bleue(lab, n):
    """Un bleu unique par îlot, le plus contrasté possible avec ses voisins."""
    pal = np.zeros((n + 1, 3), np.uint8)
    if n == 0:
        return pal
    cand = nuances_bleues(max(n, 2) * 3 if n < 200 else n)
    labc = cv2.cvtColor(cand[None], cv2.COLOR_RGB2LAB)[0].astype(np.float32)
    paires = set()  # îlots qui se touchent (ils se rejoignent sous le trait)
    for x, y in ((lab[:, 1:], lab[:, :-1]), (lab[1:], lab[:-1])):
        m = (x != y) & (x > 0) & (y > 0)
        paires.update(zip(x[m].tolist(), y[m].tolist()))
    voisins = {i: set() for i in range(1, n + 1)}
    for p, q in paires:
        voisins[p].add(q)
        voisins[q].add(p)
    aires = np.bincount(lab.ravel(), minlength=n + 1)
    libre = np.ones(len(cand), bool)
    choisi = {}
    for z in sorted(range(1, n + 1), key=lambda z: -aires[z]):
        idx = np.flatnonzero(libre)
        deja = [choisi[v] for v in voisins[z] if v in choisi]
        if deja:
            d = np.linalg.norm(labc[idx, None] - labc[deja][None], axis=2).min(axis=1)
            k = idx[np.argmax(d)]
        else:
            k = idx[0]
        choisi[z] = k
        libre[k] = False
        pal[z] = cand[k]
    return pal


# ---------------------------------------------------------------- résultat

@dataclass
class Resultat:
    trait: np.ndarray    # RVBA uint8 : le dessin sans papier
    lab: np.ndarray      # int32 : numéro d'îlot par pixel (0 = extérieur)
    n: int               # nombre d'îlots
    palette: np.ndarray  # (n+1, 3) : bleus de départ

    def zone_en(self, xr, yr):
        """Numéro d'îlot à une position relative (0-1) ; 0 si extérieur."""
        h, w = self.lab.shape
        x = min(w - 1, max(0, int(xr * w)))
        y = min(h - 1, max(0, int(yr * h)))
        return int(self.lab[y, x])

    def aplats(self, peintures=()):
        """Calque Aplats en RVBA.

        peintures : liste de (x relatif, y relatif, (r, g, b)) — un clic de pot de
        peinture. On mémorise l'endroit cliqué, pas le numéro d'îlot : après un
        recalcul (autres réglages, guides), la couleur retombe dans la bonne zone.
        """
        pal = self.palette.copy()
        for xr, yr, rgb in peintures:
            z = self.zone_en(xr, yr)
            if z > 0:
                pal[z] = rgb
        return np.dstack([pal[self.lab], np.where(self.lab > 0, 255, 0).astype(np.uint8)])


def zone_entouree(contour, fermeture=4):
    """Contour tracé à main levée → zone pleine (le contour et tout son intérieur).

    Le trait est d'abord un peu épaissi pour refermer une boucle presque fermée.
    Une boucle restée ouverte ne remplit rien : seul le trait lui-même compte.
    """
    from scipy import ndimage
    if contour is None or not contour.any():
        return None
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * fermeture + 1,) * 2)
    epais = cv2.dilate(contour.astype(np.uint8), k) > 0
    return ndimage.binary_fill_holes(epais)


def calculer(rgb, trous=2, seuil=0.35, eclairage=True, balance=0.15, guides=None, passages=None,
             exclusions=None):
    """Image RVB → Resultat. Masques booléens de même taille que l'image :
    guides (« fermer ici »), passages (« ouvrir ici ») et exclusions (zones dont
    tout le trait est ignoré pour le découpage, ex. le texte d'une bulle)."""
    if exclusions is not None:
        passages = exclusions if passages is None else (passages | exclusions)
    trait = blanc_vers_alpha(rgb, eclairage, balance)
    lab, n = zones(trait[..., 3], trous=trous, seuil=seuil, guides=guides, passages=passages)
    trait_u8 = (trait * 255).round().astype(np.uint8)
    # Sous les pixels entièrement transparents, la couleur est invisible mais vaut
    # n'importe quoi (restes du calcul) : la mettre à zéro divise le poids du PSD.
    trait_u8[trait_u8[..., 3] == 0, :3] = 0
    return Resultat(trait_u8, lab, n, palette_bleue(lab, n))


# ---------------------------------------------------------------- export

def fusion(fond, dessus):
    """Superpose deux images RVBA (uint8)."""
    a = dessus[..., 3:4].astype(np.float32) / 255
    b = fond[..., 3:4].astype(np.float32) / 255
    ao = a + b * (1 - a)
    c = (dessus[..., :3] * a + fond[..., :3] * b * (1 - a)) / np.maximum(ao, 1e-6)
    return np.dstack([c, ao * 255]).astype(np.uint8)


def image_finie(res, aplat):
    """Aplats + trait sur papier blanc : l'image telle qu'on la verrait imprimée."""
    h, w = aplat.shape[:2]
    papier = np.full((h, w, 4), 255, np.uint8)
    return fusion(fusion(papier, aplat), res.trait)


def ilots_separes(lab, aplat, nom="Zone"):
    """Un morceau recadré par îlot : [(nom, rgba, haut, gauche)], du plus grand au plus petit.

    Basé sur les numéros d'îlots (et non les couleurs), donc deux îlots peints de la
    même couleur restent bien deux calques distincts.
    """
    from scipy import ndimage
    morceaux = []
    for i, sl in enumerate(ndimage.find_objects(lab), start=1):
        if sl is None:
            continue
        m = lab[sl] == i
        c = np.zeros(m.shape + (4,), np.uint8)
        c[m] = aplat[sl][m]
        morceaux.append((c, sl[0].start, sl[1].start, int(m.sum())))
    morceaux.sort(key=lambda t: -t[3])
    return [(f"{nom} {k:03d}", c, y, x) for k, (c, y, x, _) in enumerate(morceaux, start=1)]


def ecrire_psd(chemin, calques, fusionnee):
    """Écrit un PSD RVB avec transparence : de vrais calques, sans masque de calque.

    calques   : liste du haut vers le bas de (nom, contenu, visible) où contenu est
                une image RVBA plein format, ou une liste [(nom, rgba, haut, gauche)]
                qui devient un groupe de calques recadrés.
    fusionnee : image RVBA de l'ensemble (aperçu lu par les visionneuses et miniatures).
    """
    from PIL import Image
    from psd_tools import PSDImage
    from psd_tools.api.layers import Group, PixelLayer
    h, w = fusionnee.shape[:2]
    # Mode « RGBA » = RVB + canal de transparence par calque. En mode « RGB »,
    # psd-tools stockerait la transparence comme masque de calque.
    psd = PSDImage.new("RGBA", (w, h))
    for nom, contenu, visible in reversed(calques):  # empilement du bas vers le haut
        if isinstance(contenu, list):
            groupe = Group.new(psd, nom, open_folder=False)
            for sous_nom, img, y, x in reversed(contenu):
                PixelLayer.frompil(Image.fromarray(img, "RGBA"), groupe, sous_nom, y, x)
            groupe.visible = visible
        else:
            calque = PixelLayer.frompil(Image.fromarray(contenu, "RGBA"), psd, nom)
            calque.visible = visible
    # image fusionnée écrite à la main (celle de psd-tools a une transparence nulle),
    # compressée en RLE comme le fait Photoshop : non compressée, elle pèserait
    # largeur × hauteur × 4 octets, soit l'essentiel du fichier.
    from psd_tools.constants import Compression
    psd._record.image_data.compression = Compression.RLE
    psd._record.image_data.set_data(
        [np.ascontiguousarray(fusionnee[..., i]).tobytes() for i in range(4)], psd._record.header)
    psd.save(str(chemin))


def ecrire_ora(chemin, calques, fusionnee):
    """OpenRaster (Krita, GIMP, MyPaint). Les groupes sont aplatis en un calque."""
    def png(rgba):
        return cv2.imencode(".png", cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGRA))[1].tobytes()
    h, w = fusionnee.shape[:2]
    pile = "".join(
        f'  <layer name="{nom}" src="data/{i}.png" x="0" y="0" opacity="1.0" '
        f'visibility="{"visible" if vis else "hidden"}"/>\n'
        for i, (nom, _, vis) in enumerate(calques))
    xml = (f'<?xml version="1.0" encoding="UTF-8"?>\n<image version="0.0.3" w="{w}" h="{h}">\n'
           f' <stack>\n{pile} </stack>\n</image>\n')
    t = 256 / max(h, w)
    pouce = cv2.resize(fusionnee, (max(1, int(w * t)), max(1, int(h * t))), interpolation=cv2.INTER_AREA)
    with zipfile.ZipFile(chemin, "w") as z:
        z.writestr("mimetype", "image/openraster", compress_type=zipfile.ZIP_STORED)
        z.writestr("stack.xml", xml, compress_type=zipfile.ZIP_DEFLATED)
        for i, (_, c, _) in enumerate(calques):
            z.writestr(f"data/{i}.png", png(c))
        z.writestr("mergedimage.png", png(fusionnee))
        z.writestr("Thumbnails/thumbnail.png", png(pouce))


def enregistrer(sortie, res, peintures=(), guides=None, passages=None,
                un_calque_par_ilot=False, langue="fr", exclusions=None):
    """Enregistre le PSD (ou .ora selon l'extension de sortie)."""
    noms = NOMS_CALQUES.get(langue, NOMS_CALQUES["fr"])
    aplat = res.aplats(peintures)
    h, w = aplat.shape[:2]
    papier = np.full((h, w, 4), 255, np.uint8)
    est_psd = Path(sortie).suffix.lower() != ".ora"
    contenu_aplats = ilots_separes(res.lab, aplat, noms["zone"]) if (un_calque_par_ilot and est_psd) else aplat
    calques = [(noms["trait"], res.trait, True), (noms["aplats"], contenu_aplats, True),
               (noms["papier"], papier, True)]
    # aides gardées pour mémoire, dans des calques masqués
    for cle, m, coul in (("exclusions", exclusions, COULEUR_EXCLUSION),
                         ("passages", passages, COULEUR_PASSAGE), ("guides", guides, COULEUR_GUIDE)):
        if m is not None and m.any():
            g = np.zeros((h, w, 4), np.uint8)
            g[m] = (*coul, 255)
            calques.insert(0, (noms[cle], g, False))
    fusionnee = image_finie(res, aplat)
    if est_psd:
        ecrire_psd(sortie, calques, fusionnee)
    else:
        ecrire_ora(sortie, calques, fusionnee)


def enregistrer_png(sortie, res, peintures=()):
    """Image finie (papier + aplats + trait) en PNG."""
    ok, buf = cv2.imencode(".png", cv2.cvtColor(image_finie(res, res.aplats(peintures)), cv2.COLOR_RGBA2BGRA))
    Path(sortie).write_bytes(buf.tobytes())


# ---------------------------------------------------------------- palettes

# Palette complète, rangée par familles (clair → foncé dans chaque famille)
FAMILLES_COMPLETE = {
    "neutrals": ["#FFFFFF", "#F8F9FA", "#E9ECEF", "#CED4DA", "#8C959E", "#495057", "#212529", "#0B0C10"],
    "warm_neutrals": ["#FDFBF7", "#EFE6DD", "#D8C3B5", "#C4A484", "#B87D60", "#8D493A", "#4A2E2B"],
    "blues": ["#E0F2FE", "#7DD3FC", "#38BDF8", "#2563EB", "#1D4ED8", "#1E3A8A", "#0F172A"],
    "greens": ["#D1FAE5", "#98A886", "#10B981", "#65A30D", "#15803D", "#064E3B"],
    "yellows_oranges": ["#FEF08A", "#FACC15", "#D97706", "#FFEDD5", "#F97316", "#C2410C"],
    "pinks_reds_purples": ["#FCE7F3", "#EC4899", "#EF4444", "#881337", "#C084FC", "#581C87"],
}
PALETTE_COMPLETE = [c for famille in FAMILLES_COMPLETE.values() for c in famille]

# Palette simple (la première de ColorInk)
PALETTE_SIMPLE = ["#f4d03f", "#f39c12", "#e74c3c", "#c0392b", "#f5b7b1", "#8e44ad",
                  "#3498db", "#1abc9c", "#27ae60", "#a04000", "#f0e6d2", "#7f8c8d",
                  "#2c3e50", "#ffffff"]

PALETTES = {"complete": PALETTE_COMPLETE, "simple": PALETTE_SIMPLE}
PALETTE_DEFAUT = PALETTE_COMPLETE


def lire_gpl(chemin):
    """Lit une palette GIMP / Krita (.gpl) → liste de couleurs « #rrggbb »."""
    couleurs = []
    for ligne in Path(chemin).read_text(encoding="utf-8", errors="replace").splitlines():
        ligne = ligne.strip()
        if not ligne or ligne.startswith("#") or ":" in ligne.split()[0] or ligne.startswith("GIMP"):
            continue
        parts = ligne.split()
        try:
            r, g, b = (int(v) for v in parts[:3])
        except ValueError:
            continue
        if all(0 <= v <= 255 for v in (r, g, b)):
            c = f"#{r:02x}{g:02x}{b:02x}"
            if c not in couleurs:
                couleurs.append(c)
    return couleurs


# ---------------------------------------------------------------- ligne de commande

def traiter(chemin, trous=3, seuil=0.35, eclairage=True, balance=0.15, ext=".psd",
            un_calque_par_ilot=False, langue="fr"):
    res = calculer(charger(chemin), trous, seuil, eclairage, balance)
    sortie = chemin.with_name(chemin.stem + SUFFIXE + ext)
    enregistrer(sortie, res, un_calque_par_ilot=un_calque_par_ilot, langue=langue)
    print(f"{chemin.name} → {sortie.name}  ({res.n} zones)")
    return sortie, res.n


def main():
    p = argparse.ArgumentParser(description="ColorInk : trait sans papier + un aplat par forme fermée (.psd)")
    p.add_argument("entrees", nargs="+", type=Path, help="images ou dossiers")
    p.add_argument("--trous", type=int, default=3,
                   help="taille des trous à fermer dans le trait, en pixels (0 = aucun, défaut 3)")
    p.add_argument("--seuil", type=float, default=0.35,
                   help="à partir de quelle densité d'encre un pixel compte comme trait (0-1)")
    p.add_argument("--balance", type=float, default=0.15,
                   help="0 = garde les gris ; plus haut = enlève davantage le papier gris/ombré (0-0.9)")
    p.add_argument("--sans-eclairage", action="store_true",
                   help="désactive la correction d'éclairage (scans bien uniformes)")
    p.add_argument("--calques", action="store_true", help="un calque par îlot (groupe Aplats)")
    p.add_argument("--ora", action="store_true", help="format OpenRaster au lieu de PSD")
    p.add_argument("--en", action="store_true", help="noms de calques en anglais")
    a = p.parse_args()

    fichiers = []
    for e in a.entrees:
        if e.is_dir():
            fichiers += sorted(f for f in e.iterdir() if f.suffix.lower() in EXTS
                               and not f.stem.endswith(SUFFIXE))
        else:
            fichiers.append(e)
    if not fichiers:
        sys.exit("Aucune image trouvée.")
    for f in fichiers:
        try:
            traiter(f, a.trous, a.seuil, not a.sans_eclairage, a.balance,
                    ".ora" if a.ora else ".psd", a.calques, "en" if a.en else "fr")
        except Exception as ex:
            print(f"{f.name} : erreur — {ex}", file=sys.stderr)


if __name__ == "__main__":
    main()
