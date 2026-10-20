ColorInk — scan · clean · add layers for colours
Copyright (c) 2026 Martin Guillaumie — MIT licence (see LICENSE)
=====================================================================

ColorInk prepares an ink drawing for colouring: it removes the paper from a
photo or a scan, creates one flat colour per closed shape, and exports a
layered PSD (Line art / Flats / Paper).

Illustrated user guide: docs/guide.html (or the "How to" button in the app).
Click "English" at the top of the app to switch the interface language.


RUN
---
The first run needs an Internet connection: the launcher installs "uv",
which downloads Python and the libraries. This takes a few minutes, once.

  Linux (tested): open a terminal in this folder and type
      sh lancer.sh
  A "ColorInk" shortcut then appears in the applications menu.

  Windows: extract the ZIP, then double-click lancer.bat
           (a "ColorInk" shortcut is added to the desktop)
  macOS:   double-click lancer.command

  Windows and macOS (Intel) pass an automated test on fresh machines;
  the double-click and the Windows or macOS security warnings have not
  been tried by a person.

The app opens in your browser (address http://127.0.0.1:7860).
To stop it: close the terminal if you started it with "sh lancer.sh".
Started from the menu shortcut, it runs without a terminal window: it stops
when the computer restarts, or with the command
      pkill -f interface.py


USE
---
1. Drawing: drop the photo or scan.
2. Paper: keep "Correct the lighting" ticked for a photo; raise the balance
   if grey paper remains, lower it if thin lines disappear.
3. Zones: a checkerboard zone in the preview has "leaked" through a gap in
   the line. Increase "Gap closing", or close the gap by hand in the
   Guides tab.
4. Guides (optional):
     Close (red)      splits two zones
     Open (green)     merges two zones
     Exclude (purple) circle an area to ignore it (speech bubble text…)
     Eraser           erases guides
   Then go back to "Preview": the computation happens then.
   Guides do not appear in the result.
5. Colours (optional): pick a colour, click a zone.
   Unpainted zones stay blue.
6. Export: "Create the PSD and the final image", then download.
   "One layer per island" puts each zone on its own layer.

The PSD files open in Krita and GIMP (checked with Krita 5.2 and GIMP 2.10).


PRIVACY
-------
Once installed, ColorInk makes no outside connections.
Your drawings stay on your computer.
