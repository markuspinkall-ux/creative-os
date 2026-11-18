#!/bin/sh
# Lösungsbuch Ocarina of Time – nur für diesen Benutzer installieren (kein sudo nötig).
set -eu
QUELLE="$(cd "$(dirname "$0")" && pwd)"
ZIEL="$HOME/.local/share/orbit-loesungsbuch"
mkdir -p "$ZIEL" "$HOME/.local/share/applications" "$HOME/.local/share/icons/hicolor/scalable/apps"
cp "$QUELLE/index.html" "$QUELLE/loesungsbuch.py" "$QUELLE/orbit-loesungsbuch.svg" "$ZIEL/"
cp "$QUELLE/deinstallieren.sh" "$ZIEL/"
cp "$QUELLE/orbit-loesungsbuch.svg" "$HOME/.local/share/icons/hicolor/scalable/apps/"
cat > "$HOME/.local/share/applications/orbit-loesungsbuch.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Lösungsbuch Ocarina of Time
GenericName=Lösungsbuch
Comment=Komplettlösung für das Switch-2-Remake: Lösungsweg, Karten, Lieder, Endgegner, Sammeln
Keywords=Zelda;Ocarina;Lösung;Walkthrough;Switch;
Exec=python3 $ZIEL/loesungsbuch.py
Icon=orbit-loesungsbuch
Terminal=false
Categories=Game;
StartupWMClass=orbit-loesungsbuch
DESKTOP
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$HOME/.local/share/applications" >/dev/null 2>&1 || true
echo "Lösungsbuch installiert – du findest es im Startmenü unter „Lösungsbuch Ocarina of Time“."
