#!/bin/sh
# ColorInk — lanceur Linux / macOS
# Copyright (c) 2026 Martin Guillaumie — licence MIT
#
# Au premier lancement : installe « uv » (gestionnaire Python autonome) si besoin,
# qui télécharge ensuite tout seul Python et les bibliothèques (quelques minutes).
# Les fois suivantes, l'application démarre directement.
cd "$(dirname "$0")" || exit 1
ICI="$(pwd)"

UV="$(command -v uv 2>/dev/null)"
[ -z "$UV" ] && [ -x "$HOME/.local/bin/uv" ] && UV="$HOME/.local/bin/uv"
if [ -z "$UV" ]; then
    echo "Première utilisation : installation de uv…  /  First run: installing uv…"
    if command -v curl >/dev/null 2>&1; then
        curl -LsSf https://astral.sh/uv/install.sh | sh
    elif command -v wget >/dev/null 2>&1; then
        wget -qO- https://astral.sh/uv/install.sh | sh
    else
        echo "Il faut curl ou wget pour installer uv.  /  curl or wget is required." ; exit 1
    fi
    UV="$HOME/.local/bin/uv"
    [ -x "$UV" ] || { echo "Échec de l'installation de uv.  /  uv installation failed."; exit 1; }
fi

# Linux : raccourci dans le menu des applications (réécrit à chaque lancement,
# pour suivre un déplacement du dossier ou une nouvelle icône)
RACCOURCI="$HOME/.local/share/applications/colorink.desktop"
if [ "$(uname)" = "Linux" ]; then
    [ -f "$RACCOURCI" ] || NOUVEAU=1
    mkdir -p "$(dirname "$RACCOURCI")"
    cat > "$RACCOURCI" <<EOD
[Desktop Entry]
Type=Application
Name=ColorInk
Comment=Scanne · nettoie · ajoute des calques pour les couleurs
Exec=sh "$ICI/lancer.sh"
Icon=$ICI/images/icone.png
Terminal=false
Categories=Graphics;
EOD
    [ -n "$NOUVEAU" ] && echo "Raccourci « ColorInk » ajouté au menu des applications."
fi

echo "Démarrage de ColorInk…  /  Starting ColorInk…"
exec "$UV" run --project "$ICI" python "$ICI/interface.py"
