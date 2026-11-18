#!/bin/sh
# Lösungsbuch wieder entfernen (Fortschritt wird mit gelöscht).
set -eu
rm -f "$HOME/.local/share/applications/orbit-loesungsbuch.desktop" \
      "$HOME/.local/share/icons/hicolor/scalable/apps/orbit-loesungsbuch.svg"
rm -rf "$HOME/.local/share/orbit-loesungsbuch"
echo "Lösungsbuch entfernt."
