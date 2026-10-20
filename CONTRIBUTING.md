# Taking ColorInk further

Notes for anyone who wants to change or continue the project: how it is built, why some choices were made, and the places where a mistake breaks something silently.
*Version française : [CONTINUER.md](CONTINUER.md). The code and its comments are in French.*

## Files

| File | Role |
|---|---|
| `colorink.py` | The core, no UI: paper → transparency, zone detection, palette, PSD / ORA / PNG export. Usable alone from the command line. |
| `interface.py` | The Gradio app (3 columns, Preview / Guides / Colours tabs, export). |
| `textes.py` | All interface texts, in French and English. To add a language, copy the `"en"` block. |
| `editeur_guides.js` | The guide editor (Close / Open / Exclude / Eraser), inside a `gr.HTML` component. |
| `peinture.js` | The paint bucket, running in the browser. |
| `docs/guide.html` | The user guide, generated: do not edit by hand. |
| `docs/source/` | The guide template (`modele_guide.html`), its images and `construire_guide.py`, which builds `docs/guide.html` with embedded images. |
| `images/` | Logo, icon (`.png` for Linux and the browser tab, `.ico` for Windows). |
| `polices/` | Outfit font (SIL OFL 1.1), served locally. |
| `lancer.sh`, `lancer.command`, `lancer.bat` | uv launchers (Linux / macOS / Windows), tested automatically by `.github/workflows/test-lanceurs.yml`. |
| `pyproject.toml`, `.python-version`, `requirements.txt` | Dependencies (uv reads the first two, pip the last). |

After changing the guide: `python docs/source/construire_guide.py`.

## The pipeline

```
image → estimated paper background → line alpha → threshold + red guides → gap closing
      → green openings and exclusions removed → connected components → islands → flats under the line → PSD
```

1. **Paper → transparency** (`fond_papier`, `blanc_vers_alpha`): the background is estimated on a reduced copy (800 px) with dilation, erosion and blur, which corrects the shadows and gradients of a photo. Alpha = 1 − min(pixel / paper); the *balance* acts as a threshold.
2. **Zones** (`zones`): red guides are added to the thresholded line, then a dilation the size of the gaps; green guides and excluded areas are removed. `cv2.connectedComponents` with 4-connectivity. Components touching the border are the outside; tiny ones are dropped. `expand_labels` (scikit-image) grows the islands under the line so no halo is left.
3. **Exclusions** (`zone_entouree`): the purple stroke is dilated, then `binary_fill_holes` gives the enclosed area.
4. **Blue palette** (`nuances_bleues`, `palette_bleue`): shades from a Halton sequence, assigned to maximise the (LAB) contrast between neighbouring islands.
5. **Colours**: clicks are stored in relative coordinates `(x, y, rgb)` and reapplied by `Resultat.aplats(peintures)`, so they survive a change of setting or guide.
6. **Export** (`enregistrer`, `ecrire_psd`): Line art / Flats (or a group with one layer per island) / Paper, plus hidden helper layers.

## Choices and pitfalls

**PSD**
- `PSDImage.new("RGBA")`, not `"RGB"`: in RGB mode, psd-tools adds a mask to every layer.
- The merged image is written by hand, RLE-compressed. Without it a PSD weighed about 60 MB; with it, 3 to 8 MB.
- Colour is zeroed under fully transparent pixels: invisible, but compression gains a lot.
- Checked in Krita 5.2 and GIMP 2.10: all layers, no masks, helper layers hidden, identical rendering (max difference of 1 out of 255). Check again after any change to `ecrire_psd`.
- psd-tools ≥ 1.25 requires Python ≥ 3.11.

**Gradio (version 6)**
- Guides and painting are custom `gr.HTML` components (`js_on_load`, `props`). The JS UI is kept on the element and re-attached by a `setInterval` loop (120 to 150 ms), because Gradio may recreate the DOM.
- An `undefined` prop is ignored on the JS side.
- **Every update of an HTML component sends its full state** (background + language; data + palette + language). A component in a lazily mounted tab only sees the last update; `render_children` was not enough.
- Guide strokes arrive through the `input` event; the computation only runs when going back to the Preview tab, so drawing stays smooth.
- The language toggle (`basculer`) updates about thirty components: when adding a translated component, add it to its outputs too.

**Painting in the browser**
- Python sends once: a PNG of the zones (island number = R + G×256), the line PNG, the blues, an index of pixels per zone. Filling is then done in JS, in under 10 ms. Going back to a Python round trip per click would make every fill slow.

**Privacy**
- `GRADIO_ANALYTICS_ENABLED=False` and `HF_HUB_DISABLE_TELEMETRY=1` are set **before** `import gradio`, plus `analytics_enabled=False`.
- The font is served from `polices/` (no Google Fonts).
- Checked: no outside request during a full session. Check again after a Gradio update.

**Built-in guide**
- Served by Gradio through `gr.set_static_paths` at `/gradio_api/file=…`. The "Back to ColorInk" button only shows at that address; it closes the tab (opened with `rel="opener"`) or goes back.

## Known limits

- The Windows and macOS launchers pass the automated test on GitHub's machines (Windows Server, Intel macOS). Double-click, SmartScreen, Gatekeeper and Apple-silicon Macs still need trying by a person.
- The preview works on a reduced image, but export recomputes everything at full resolution: very large images can take time and memory.
- Very faint or very irregular lines need guides drawn by hand.

## Ideas

- Add Apple-silicon Macs (`macos-latest`) to the test when GitHub has free machines: at the time of writing they were never available.
- A real app window (pywebview) or Chrome's app mode, instead of a browser tab.
- An online demo (Hugging Face Spaces): handy, but drawings would then leave the user's computer. Say so clearly if someone sets one up.
