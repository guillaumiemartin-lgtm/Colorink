// ColorInk — pot de peinture (onglet « Couleurs »)
// Copyright (c) 2026 Martin Guillaumie — licence MIT (voir LICENSE)
//
// Composant gr.HTML : le remplissage se fait entièrement dans le navigateur, donc
// sans attente. Python envoie, après chaque calcul des zones :
//   props.donnees = JSON { id, w, h, zones (PNG : numéro d'îlot = R + G×256),
//                          trait (PNG RVBA), bleus ([[r,g,b], …] par numéro d'îlot) }
//   props.palette = JSON [ "#rrggbb", … ]       props.langue = "fr" | "en"
// et reçoit dans props.value la liste des clics : JSON [[x, y, "#rrggbb"], …]
// (x, y relatifs 0-1). C'est l'endroit cliqué qui est mémorisé, pas le numéro
// d'îlot : si les zones sont recalculées, chaque couleur retombe au bon endroit.
//
// Gradio peut vider le conteneur quand Python met à jour une propriété : l'interface
// est gardée en mémoire (element._cp) et remise en place si elle disparaît.

if (!element._cp) {
  const TXT = {
    fr: { autre: "Autre couleur", annuler: "Annuler", effacer: "Tout effacer", ajuster: "Ajuster",
          zoom: "Zoom : − / + ou Ctrl + molette",
          vide: "Déposez un dessin dans la fenêtre Dessin.",
          peint: (k) => `${k} zone(s) peinte(s).`,
          dehors: "Ce clic est en dehors des zones (fond extérieur) : rien à remplir.",
          calcul: "Calcul des zones…" },
    en: { autre: "Other colour", annuler: "Undo", effacer: "Clear all", ajuster: "Fit",
          zoom: "Zoom: − / + or Ctrl + wheel",
          vide: "Drop a drawing in the Drawing panel.",
          peint: (k) => `${k} zone(s) painted.`,
          dehors: "This click is outside the zones (background): nothing to fill.",
          calcul: "Computing zones…" },
  };

  const ui = document.createElement("div");
  ui.className = "ci-peinture";
  ui.innerHTML = `
    <style>
      .ci-peinture { --b:#ef4444; color:var(--b); font-family:inherit; user-select:none; }
      .ci-p-haut { display:flex; flex-wrap:wrap; gap:10px; align-items:flex-start; margin-bottom:10px; }
      .ci-pastilles { display:grid; grid-template-columns:repeat(auto-fill, 28px); gap:5px; flex:1 1 300px;
                      border:2px solid var(--b); padding:6px; max-height:136px; overflow-y:auto; }
      .ci-pastille { width:28px; height:28px; border:2px solid var(--b); cursor:pointer; padding:0; }
      .ci-pastille.choisie { outline:3px solid var(--b); outline-offset:1px; }
      .ci-p-cote { display:flex; flex-direction:column; gap:6px; min-width:170px; font-size:12px; }
      .ci-p-cote label { display:flex; align-items:center; gap:8px; }
      .ci-p-cote input[type=color] { width:44px; height:28px; border:2px solid var(--b); padding:0 2px;
                                     background:#fff; cursor:pointer; }
      .ci-actuelle { width:44px; height:28px; border:2px solid var(--b); display:inline-block; }
      .ci-peinture button.ci-p-bouton { border:2px solid var(--b) !important; background:#fff !important;
        color:var(--b) !important; font:inherit; font-size:12px !important; font-weight:700 !important;
        padding:4px 10px !important; border-radius:0 !important; cursor:pointer; min-width:0 !important;
        box-shadow:2px 2px 0 var(--b) !important; height:auto !important; margin:0 !important; }
      .ci-peinture button.ci-p-bouton:hover { background:#fde8e8 !important; }
      .ci-p-vue { border:2px solid var(--b); background:#f4f4f4; min-height:200px; max-height:640px;
                  overflow:auto; position:relative; }
      .ci-p-vue.vide { display:flex; justify-content:center; align-items:center; font-size:13px; }
      .ci-p-vue canvas { cursor:crosshair; display:block; margin:0 auto; background:#fff; }
      .ci-p-zoom { display:flex; gap:4px; align-items:center; }
      .ci-p-zoom small { font-size:11px; opacity:.8; margin-left:4px; }
      .ci-p-msg { font-size:12px; margin-top:8px; min-height:1.2em; }
    </style>
    <div class="ci-p-haut">
      <div class="ci-pastilles"></div>
      <div class="ci-p-cote">
        <label><span class="ci-actuelle"></span><input type="color" class="ci-autre" value="#ef4444">
               <span data-t="autre"></span></label>
        <div style="display:flex; gap:6px;">
          <button class="ci-p-bouton ci-annuler" data-t="annuler"></button>
          <button class="ci-p-bouton ci-effacer" data-t="effacer"></button>
        </div>
        <div class="ci-p-zoom">
          <button class="ci-p-bouton ci-moins">−</button>
          <button class="ci-p-bouton ci-ajuster" data-t="ajuster"></button>
          <button class="ci-p-bouton ci-plus">+</button>
        </div>
        <small data-t="zoom"></small>
      </div>
    </div>
    <div class="ci-p-vue vide"><span class="ci-p-vide" data-t="vide"></span></div>
    <div class="ci-p-msg"></div>`;

  const vue = ui.querySelector(".ci-p-vue");
  const msg = ui.querySelector(".ci-p-msg");
  const actuelle = ui.querySelector(".ci-actuelle");
  const autre = ui.querySelector(".ci-autre");
  const toile = document.createElement("canvas");
  const S = {
    couleur: "#ef4444", clics: [], langue: "fr", zoom: 1, largeurVue: 0,
    donneesSrc: null, paletteSrc: null, id: null,
    w: 0, h: 0, zones: null, trait: null, bleus: [], parZone: null, sortie: null, pret: false,
  };
  const T = () => TXT[S.langue] || TXT.fr;

  // ------------------------------------------------------------ couleurs
  function hexVersRgb(c) {
    c = (c || "#000").replace("#", "");
    if (c.length === 3) c = c.split("").map((x) => x + x).join("");
    return [0, 2, 4].map((i) => parseInt(c.substr(i, 2), 16) || 0);
  }
  function choisir(c) {
    S.couleur = c.toLowerCase();
    actuelle.style.background = S.couleur;
    autre.value = S.couleur.length === 7 ? S.couleur : "#000000";
    ui.querySelectorAll(".ci-pastille").forEach((p) => p.classList.toggle("choisie", p.dataset.c === S.couleur));
  }
  function remplirPalette(liste) {
    const boite = ui.querySelector(".ci-pastilles");
    boite.innerHTML = "";
    for (const c of liste) {
      const b = document.createElement("button");
      b.className = "ci-pastille"; b.dataset.c = c.toLowerCase(); b.title = c;
      b.style.background = c;
      b.addEventListener("click", () => choisir(c));
      boite.appendChild(b);
    }
    choisir(S.couleur);
  }
  autre.addEventListener("input", () => choisir(autre.value));

  // ------------------------------------------------------------ zones
  function decoder(src) {
    return new Promise((ok, ko) => {
      const img = new Image();
      img.onload = () => {
        const c = document.createElement("canvas"); c.width = img.naturalWidth; c.height = img.naturalHeight;
        const ctx = c.getContext("2d", { willReadFrequently: true });
        ctx.drawImage(img, 0, 0);
        ok(ctx.getImageData(0, 0, c.width, c.height).data);
      };
      img.onerror = ko; img.src = src;
    });
  }

  async function chargerDonnees(json) {
    S.donneesSrc = json;
    if (!json) { S.pret = false; vue.classList.add("vide"); vue.innerHTML = ""; vue.append(texteVide);
                 msg.textContent = ""; return; }
    let d; try { d = JSON.parse(json); } catch (e) { return; }
    const [z, t] = await Promise.all([decoder(d.zones), decoder(d.trait)]);
    if (S.donneesSrc !== json) return;             // un calcul plus récent est arrivé entre-temps
    if (d.id !== S.id) { S.id = d.id; S.clics = []; S.zoom = 1; publier(); }
    S.w = d.w; S.h = d.h; S.bleus = d.bleus; S.trait = t;
    const n = S.w * S.h;
    S.zones = new Int32Array(n);
    for (let i = 0, j = 0; i < n; i++, j += 4) S.zones[i] = z[j] + z[j + 1] * 256;
    // index des pixels de chaque îlot (pour ne repeindre que la zone cliquée)
    const nb = S.bleus.length, compte = new Int32Array(nb + 1);
    for (let i = 0; i < n; i++) compte[S.zones[i] + 1]++;
    for (let k = 1; k <= nb; k++) compte[k] += compte[k - 1];
    const ordre = new Int32Array(n), pos = compte.slice(0, nb);
    for (let i = 0; i < n; i++) ordre[pos[S.zones[i]]++] = i;
    S.parZone = { ordre, debut: compte };
    toile.width = S.w; toile.height = S.h;
    S.sortie = toile.getContext("2d").createImageData(S.w, S.h);
    S.pret = true;
    vue.classList.remove("vide"); vue.innerHTML = ""; vue.append(toile);
    appliquerZoom();
    toutRepeindre();
    majMessage();
  }
  const texteVide = ui.querySelector(".ci-p-vide");

  function couleurDesZones() {                     // bleus de départ, puis clics dans l'ordre
    const pal = S.bleus.map((c) => c.slice());
    for (const [x, y, c] of S.clics) {
      const z = zoneEn(x, y);
      if (z > 0) pal[z] = hexVersRgb(c);
    }
    return pal;
  }
  function zoneEn(xr, yr) {                        // même calcul que Resultat.zone_en (Python)
    const x = Math.min(S.w - 1, Math.max(0, Math.floor(xr * S.w)));
    const y = Math.min(S.h - 1, Math.max(0, Math.floor(yr * S.h)));
    return S.zones[y * S.w + x];
  }
  function peindrePixel(i, c) {                    // papier blanc + aplat + trait par-dessus
    const o = S.sortie.data, t = S.trait, j = i * 4, a = t[j + 3] / 255, b = 1 - a;
    o[j] = c[0] * b + t[j] * a; o[j + 1] = c[1] * b + t[j + 1] * a; o[j + 2] = c[2] * b + t[j + 2] * a;
    o[j + 3] = 255;
  }
  function toutRepeindre() {
    const pal = couleurDesZones(), blanc = [255, 255, 255];
    for (let i = 0, n = S.w * S.h; i < n; i++) { const z = S.zones[i]; peindrePixel(i, z > 0 ? pal[z] : blanc); }
    toile.getContext("2d").putImageData(S.sortie, 0, 0);
  }
  function repeindreZone(z, c) {
    const { ordre, debut } = S.parZone;
    for (let k = debut[z]; k < debut[z + 1]; k++) peindrePixel(ordre[k], c);
    toile.getContext("2d").putImageData(S.sortie, 0, 0);
  }

  // ------------------------------------------------------------ zoom
  function appliquerZoom(cx, cy) {
    if (!S.pret) return;
    const dispoL = Math.max(200, vue.clientWidth - 4), dispoH = 636;
    const ajuste = Math.min(dispoL / S.w, dispoH / S.h, 1);
    // garder sous la souris le même point de l'image pendant le zoom
    const avant = toile.getBoundingClientRect();
    const fx = cx === undefined ? 0.5 : (cx - avant.left) / avant.width;
    const fy = cy === undefined ? 0.5 : (cy - avant.top) / avant.height;
    const k = ajuste * S.zoom;
    toile.style.width = Math.round(S.w * k) + "px";
    toile.style.height = Math.round(S.h * k) + "px";
    const apres = toile.getBoundingClientRect(), v = vue.getBoundingClientRect();
    const px = cx === undefined ? v.left + v.width / 2 : cx, py = cy === undefined ? v.top + v.height / 2 : cy;
    vue.scrollLeft += (apres.left + fx * apres.width) - px;
    vue.scrollTop += (apres.top + fy * apres.height) - py;
  }
  function zoomer(f, cx, cy) { S.zoom = Math.min(8, Math.max(1, S.zoom * f)); appliquerZoom(cx, cy); }
  ui.querySelector(".ci-plus").addEventListener("click", () => zoomer(1.5));
  ui.querySelector(".ci-moins").addEventListener("click", () => zoomer(1 / 1.5));
  ui.querySelector(".ci-ajuster").addEventListener("click", () => { S.zoom = 1; appliquerZoom(); });
  vue.addEventListener("wheel", (e) => {          // Ctrl + molette : zoom centré sur la souris
    if (!S.pret || !(e.ctrlKey || e.metaKey)) return;
    e.preventDefault();
    zoomer(e.deltaY < 0 ? 1.25 : 0.8, e.clientX, e.clientY);
  }, { passive: false });

  function publier() { props.value = S.clics.length ? JSON.stringify(S.clics) : ""; }
  function majMessage() {
    const zonesPeintes = new Set(S.clics.map(([x, y]) => zoneEn(x, y)).filter((z) => z > 0));
    msg.textContent = S.clics.length ? T().peint(zonesPeintes.size) : "";
  }

  toile.addEventListener("click", (e) => {
    if (!S.pret) return;
    const r = toile.getBoundingClientRect();
    const xr = (e.clientX - r.left) / r.width, yr = (e.clientY - r.top) / r.height;
    const z = zoneEn(xr, yr);
    if (z === 0) { msg.textContent = T().dehors; return; }
    S.clics.push([+xr.toFixed(5), +yr.toFixed(5), S.couleur]);
    repeindreZone(z, hexVersRgb(S.couleur));
    publier(); majMessage();
  });
  ui.querySelector(".ci-annuler").addEventListener("click", () => {
    if (!S.clics.length) return;
    S.clics.pop(); if (S.pret) toutRepeindre(); publier(); majMessage();
  });
  ui.querySelector(".ci-effacer").addEventListener("click", () => {
    S.clics = []; if (S.pret) toutRepeindre(); publier(); majMessage();
  });

  function traduire() {
    ui.querySelectorAll("[data-t]").forEach((n) => { n.textContent = T()[n.dataset.t]; });
    if (S.pret) majMessage();
  }

  // ------------------------------------------------------------ surveillance
  element._cp = ui;
  setInterval(() => {
    if (!element.contains(ui)) element.appendChild(ui);
    // une propriété absente (undefined) n'est pas une remise à zéro : on garde la dernière valeur
    if (props.palette !== undefined && (props.palette || "") !== (S.paletteSrc || "")) {
      S.paletteSrc = props.palette || "";
      try { remplirPalette(JSON.parse(S.paletteSrc || "[]")); } catch (e) { console.warn("ColorInk palette :", e); }
    }
    if (props.donnees !== undefined && (props.donnees || "") !== (S.donneesSrc || "")) chargerDonnees(props.donnees || "");
    if (props.langue !== undefined && props.langue !== S.langue) { S.langue = props.langue || "fr"; traduire(); }
    if (S.pret && toile.isConnected && Math.abs(vue.clientWidth - S.largeurVue) > 2) {
      S.largeurVue = vue.clientWidth; appliquerZoom();   // onglet affiché ou fenêtre redimensionnée
    }
  }, 120);
  S.langue = props.langue || "fr";
  traduire();
  choisir(S.couleur);
  element.appendChild(ui);
}
