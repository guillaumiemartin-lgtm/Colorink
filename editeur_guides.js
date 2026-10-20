// ColorInk — éditeur de guides (onglet « Guides »)
// Copyright (c) 2026 Martin Guillaumie — licence MIT (voir LICENSE)
//
// Composant gr.HTML : ce code est exécuté par Gradio avec `element` (le conteneur)
// et `props` (props.fond = image de fond en data URL, props.langue = "fr"/"en").
// À chaque trait terminé, props.value reçoit les traits seuls en PNG (data URL),
// à la taille de l'image de fond ; Python les trie ensuite par couleur.
//
// Gradio peut vider le conteneur quand Python met à jour une propriété : l'interface
// est donc gardée en mémoire (element._ci) et remise en place si elle disparaît.

if (!element._ci) {
  const OUTILS = {
    fermer:  { couleur: "#ff4628" },
    ouvrir:  { couleur: "#19c37d" },
    exclure: { couleur: "#8e44ad" },
    gomme:   { couleur: null },
  };
  const TXT = {
    fr: { fermer: "Fermer", ouvrir: "Ouvrir", exclure: "Exclure", gomme: "Gomme",
          taille: "Taille", lissage: "Lissage", annuler: "Annuler", effacer: "Tout effacer",
          ajuster: "Ajuster", vide: "Déposez un dessin dans la fenêtre Dessin." },
    en: { fermer: "Close", ouvrir: "Open", exclure: "Exclude", gomme: "Eraser",
          taille: "Size", lissage: "Smoothing", annuler: "Undo", effacer: "Clear all",
          ajuster: "Fit", vide: "Drop a drawing in the Drawing panel." },
  };

  // ------------------------------------------------------------ interface
  const ui = document.createElement("div");
  ui.className = "ci-guides";
  ui.innerHTML = `
    <style>
      .ci-guides { --b:#ef4444; font-family: inherit; color: var(--b); user-select: none; }
      .ci-barre { display:flex; flex-wrap:wrap; gap:8px; align-items:center; margin-bottom:10px; }
      .ci-guides button { font-family:inherit !important; border-radius:0 !important; min-width:0 !important;
                          height:auto !important; line-height:1.2 !important; margin:0 !important; }
      .ci-guides button.ci-outil { border:2px solid var(--b) !important; background:#fff !important;
                  color:var(--b) !important; font-weight:700 !important; font-size:14px !important;
                  padding:8px 14px !important; cursor:pointer; box-shadow:3px 3px 0 var(--b) !important;
                  display:flex !important; align-items:center; gap:8px; }
      .ci-outil i { width:12px; height:12px; display:inline-block; border:2px solid #fff;
                    box-shadow:0 0 0 1px var(--b); }
      .ci-guides button.ci-outil.actif, .ci-guides button.ci-outil.actif span { color:#fff !important; }
      .ci-guides button.ci-outil span { color:inherit !important; }
      .ci-guides button.ci-outil[data-o=fermer].actif  { background:#ff4628 !important; border-color:#ff4628 !important; box-shadow:3px 3px 0 #b8301a !important; }
      .ci-guides button.ci-outil[data-o=ouvrir].actif  { background:#19c37d !important; border-color:#19c37d !important; box-shadow:3px 3px 0 #0f7a4e !important; }
      .ci-guides button.ci-outil[data-o=exclure].actif { background:#8e44ad !important; border-color:#8e44ad !important; box-shadow:3px 3px 0 #5b2470 !important; }
      .ci-guides button.ci-outil[data-o=gomme].actif   { background:#343a40 !important; border-color:#343a40 !important; box-shadow:3px 3px 0 #111 !important; }
      .ci-reglages { display:flex; flex-wrap:wrap; gap:8px 14px; align-items:center; margin-bottom:10px; font-size:12px; }
      .ci-reglages label { display:flex; align-items:center; gap:6px; margin:0; }
      .ci-reglages input[type=range] { accent-color:var(--b); width:100px; }
      .ci-groupe { display:flex; gap:4px; }
      .ci-guides button.ci-petit { border:2px solid var(--b) !important; background:#fff !important;
                  color:var(--b) !important; font-size:12px !important; font-weight:700 !important;
                  padding:3px 9px !important; box-shadow:none !important; cursor:pointer; }
      .ci-guides button.ci-petit:hover, .ci-guides button.ci-outil:not(.actif):hover { background:#fde8e8 !important; }
      .ci-vue { position:relative; overflow:auto; max-height:640px; border:2px solid var(--b);
                background:#f4f4f4; touch-action:none; }
      .ci-vue.vide { display:flex; align-items:center; justify-content:center; height:200px; font-size:13px; }
      .ci-pile { position:relative; margin:0 auto; }
      .ci-pile canvas { position:absolute; left:0; top:0; width:100%; height:100%; }
      .ci-traits { opacity:.85; }
      .ci-curseur { position:fixed; pointer-events:none; border:2px solid #000; border-radius:50%;
                    transform:translate(-50%,-50%); display:none; z-index:50;
                    box-shadow:0 0 0 1px #fff; }
      .ci-sep { width:2px; align-self:stretch; background:var(--b); opacity:.3; }
    </style>
    <div class="ci-barre">
      <button class="ci-outil actif" data-o="fermer"><i style="background:#ff4628"></i><span></span></button>
      <button class="ci-outil" data-o="ouvrir"><i style="background:#19c37d"></i><span></span></button>
      <button class="ci-outil" data-o="exclure"><i style="background:#8e44ad"></i><span></span></button>
      <span class="ci-sep"></span>
      <button class="ci-outil" data-o="gomme"><i style="background:#fff"></i><span></span></button>
    </div>
    <div class="ci-reglages">
      <label><span data-t="taille"></span> <input type="range" class="ci-taille" min="2" max="60" value="8"></label>
      <label><span data-t="lissage"></span> <input type="range" class="ci-lissage" min="0" max="10" value="4"></label>
      <span class="ci-groupe">
        <button class="ci-petit ci-moins">−</button>
        <button class="ci-petit ci-ajuster" data-t="ajuster"></button>
        <button class="ci-petit ci-plus">+</button>
      </span>
      <span class="ci-groupe">
        <button class="ci-petit ci-annuler" data-t="annuler"></button>
        <button class="ci-petit ci-effacer" data-t="effacer"></button>
      </span>
    </div>
    <div class="ci-vue vide"><span data-t="vide"></span></div>
    <div class="ci-curseur"></div>`;

  const vue = ui.querySelector(".ci-vue");
  const curseur = ui.querySelector(".ci-curseur");
  const pile = document.createElement("div");
  pile.className = "ci-pile";
  const cFond = document.createElement("canvas");
  const cTraits = document.createElement("canvas");
  cTraits.className = "ci-traits";
  pile.append(cFond, cTraits);

  const S = {                 // état de l'éditeur
    outil: "fermer", traits: [], courant: null, zoom: 1,
    fond: null, fondSrc: null, langue: null,
    valide: document.createElement("canvas"),  // traits terminés (cache)
  };

  // ------------------------------------------------------------ dessin
  function tracer(ctx, t) {
    const p = t.points;
    if (!p.length) return;
    ctx.save();
    ctx.globalCompositeOperation = t.outil === "gomme" ? "destination-out" : "source-over";
    ctx.strokeStyle = ctx.fillStyle = t.outil === "gomme" ? "#000" : OUTILS[t.outil].couleur;
    ctx.lineWidth = t.taille;
    ctx.lineCap = ctx.lineJoin = "round";
    if (p.length === 1) {
      ctx.beginPath(); ctx.arc(p[0][0], p[0][1], t.taille / 2, 0, Math.PI * 2); ctx.fill();
    } else {
      // courbe lissée : segments quadratiques passant par les milieux
      ctx.beginPath(); ctx.moveTo(p[0][0], p[0][1]);
      for (let i = 1; i < p.length - 1; i++) {
        const mx = (p[i][0] + p[i + 1][0]) / 2, my = (p[i][1] + p[i + 1][1]) / 2;
        ctx.quadraticCurveTo(p[i][0], p[i][1], mx, my);
      }
      const d = p[p.length - 1]; ctx.lineTo(d[0], d[1]); ctx.stroke();
    }
    ctx.restore();
  }

  function reconstruire() {          // rejoue tous les traits terminés dans le cache
    const v = S.valide.getContext("2d");
    v.clearRect(0, 0, S.valide.width, S.valide.height);
    for (const t of S.traits) tracer(v, t);
    afficher();
  }

  function afficher() {
    const ctx = cTraits.getContext("2d");
    ctx.clearRect(0, 0, cTraits.width, cTraits.height);
    ctx.drawImage(S.valide, 0, 0);
    if (S.courant) tracer(ctx, S.courant);
  }

  function publier() {               // envoie les traits à Python
    props.value = S.traits.length ? S.valide.toDataURL("image/png") : "";
  }

  // ------------------------------------------------------------ fond et zoom
  function appliquerZoom() {
    if (!S.fond) return;
    const largeurDispo = Math.max(200, vue.clientWidth - 4);
    const hauteurDispo = 636;
    const ajuste = Math.min(largeurDispo / S.fond.width, hauteurDispo / S.fond.height, 1);
    const k = ajuste * S.zoom;
    pile.style.width = Math.round(S.fond.width * k) + "px";
    pile.style.height = Math.round(S.fond.height * k) + "px";
    majCurseur();
  }

  function chargerFond(src) {
    S.fondSrc = src; S.traits = []; S.courant = null; S.zoom = 1;
    if (!src) {
      S.fond = null; vue.classList.add("vide"); vue.innerHTML = ""; vue.append(texteVide);
      publier(); return;
    }
    const img = new Image();
    img.onload = () => {
      if (S.fondSrc !== src) return;
      S.fond = img;
      for (const c of [cFond, cTraits, S.valide]) { c.width = img.naturalWidth; c.height = img.naturalHeight; }
      cFond.getContext("2d").drawImage(img, 0, 0);
      vue.classList.remove("vide"); vue.innerHTML = ""; vue.append(pile);
      reconstruire(); appliquerZoom(); publier();
    };
    img.src = src;
  }
  const texteVide = ui.querySelector(".ci-vue span");

  // ------------------------------------------------------------ souris / stylet
  const echelle = () => cTraits.width / cTraits.getBoundingClientRect().width;  // px image par px écran
  function position(e) {
    const r = cTraits.getBoundingClientRect();
    return [(e.clientX - r.left) * echelle(), (e.clientY - r.top) * echelle()];
  }
  const taille = () => +ui.querySelector(".ci-taille").value;
  const lissage = () => +ui.querySelector(".ci-lissage").value;

  let pinceau = null;     // point « paresseux » qui suit la souris avec un temps de retard
  cTraits.addEventListener("pointerdown", (e) => {
    if (!S.fond || e.button !== 0) return;
    cTraits.setPointerCapture(e.pointerId);
    const p = position(e);
    pinceau = p.slice();
    S.courant = { outil: S.outil, taille: taille() * echelle(), points: [p] };
    afficher();
  });
  cTraits.addEventListener("pointermove", (e) => {
    majCurseur(e);
    if (!S.courant) return;
    const evts = e.getCoalescedEvents ? e.getCoalescedEvents() : [e];
    const rayon = lissage() * 3 * echelle();    // longueur de la « laisse », en px image
    for (const ev of evts) {
      const p = position(ev);
      const dx = p[0] - pinceau[0], dy = p[1] - pinceau[1], d = Math.hypot(dx, dy);
      if (d > rayon) {
        const f = (d - rayon) / d;
        pinceau = [pinceau[0] + dx * f, pinceau[1] + dy * f];
        const der = S.courant.points[S.courant.points.length - 1];
        if (Math.hypot(pinceau[0] - der[0], pinceau[1] - der[1]) > 0.75 * echelle())
          S.courant.points.push(pinceau.slice());
      }
    }
    afficher();
  });
  function finir(e) {
    if (!S.courant) return;
    // le pinceau lissé traîne derrière la souris : le trait rattrape le point de
    // relâchement, sinon il s'arrêterait avant (un guide ne toucherait pas le bord)
    if (e) {
      const p = position(e), der = S.courant.points[S.courant.points.length - 1];
      if (Math.hypot(p[0] - der[0], p[1] - der[1]) > 0.5) S.courant.points.push(p);
    }
    S.traits.push(S.courant); S.courant = null; pinceau = null;
    reconstruire(); publier();
  }
  cTraits.addEventListener("pointerup", finir);
  cTraits.addEventListener("pointercancel", () => { S.courant = null; afficher(); });
  cTraits.addEventListener("pointerleave", () => { curseur.style.display = "none"; });

  function majCurseur(e) {
    if (e) { S.sx = e.clientX; S.sy = e.clientY; }
    if (!S.fond || S.sx === undefined) return;
    const d = taille();
    const c = OUTILS[S.outil].couleur || "#343a40";   // gomme : gris foncé
    Object.assign(curseur.style, { display: "block", left: S.sx + "px", top: S.sy + "px",
      width: d + "px", height: d + "px", borderColor: c,
      background: S.outil === "gomme" ? "rgba(255,255,255,.5)" : "transparent" });
  }
  cTraits.style.cursor = "none";
  cTraits.addEventListener("pointerenter", majCurseur);

  // ------------------------------------------------------------ boutons
  ui.querySelectorAll(".ci-outil").forEach((b) => b.addEventListener("click", () => {
    S.outil = b.dataset.o;
    ui.querySelectorAll(".ci-outil").forEach((x) => x.classList.toggle("actif", x === b));
  }));
  ui.querySelector(".ci-annuler").addEventListener("click", () => { S.traits.pop(); reconstruire(); publier(); });
  ui.querySelector(".ci-effacer").addEventListener("click", () => { S.traits = []; reconstruire(); publier(); });
  ui.querySelector(".ci-plus").addEventListener("click", () => { S.zoom = Math.min(8, S.zoom * 1.5); appliquerZoom(); });
  ui.querySelector(".ci-moins").addEventListener("click", () => { S.zoom = Math.max(1, S.zoom / 1.5); appliquerZoom(); });
  ui.querySelector(".ci-ajuster").addEventListener("click", () => { S.zoom = 1; appliquerZoom(); });
  vue.addEventListener("wheel", (e) => {          // Ctrl + molette : zoom
    if (!S.fond || !(e.ctrlKey || e.metaKey)) return;
    e.preventDefault();
    S.zoom = Math.min(8, Math.max(1, S.zoom * (e.deltaY < 0 ? 1.25 : 0.8)));
    appliquerZoom();
  }, { passive: false });
  ui.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z") { e.preventDefault(); S.traits.pop(); reconstruire(); publier(); }
  });
  ui.tabIndex = 0;
  window.addEventListener("resize", appliquerZoom);

  function traduire(lg) {
    const T = TXT[lg] || TXT.fr;
    ui.querySelectorAll(".ci-outil").forEach((b) => { b.querySelector("span").textContent = T[b.dataset.o]; });
    ui.querySelectorAll("[data-t]").forEach((n) => { n.textContent = T[n.dataset.t]; });
  }

  // ------------------------------------------------------------ surveillance
  element._ci = ui;
  setInterval(() => {
    if (!element.contains(ui)) element.appendChild(ui);           // remis en place après un rendu
    // une propriété absente (undefined) n'est pas une remise à zéro : on garde la dernière valeur
    if (props.fond !== undefined && (props.fond || "") !== (S.fondSrc || "")) chargerFond(props.fond || "");
    if (props.langue !== undefined && props.langue !== S.langue) { S.langue = props.langue; traduire(S.langue); }
    if (S.fond && pile.isConnected && Math.abs(vue.clientWidth - (S.largeurVue || 0)) > 2) {
      S.largeurVue = vue.clientWidth; appliquerZoom();         // onglet affiché ou fenêtre redimensionnée
    }
  }, 150);
  traduire(props.langue || "fr");
  element.appendChild(ui);
}
