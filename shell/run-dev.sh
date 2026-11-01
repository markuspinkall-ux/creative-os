#!/bin/sh
# Testet die Shell direkt aus diesem Ordner – in jeder laufenden
# Desktop-Sitzung (GNOME, KDE …) als normale Fenster am unteren Rand.
cd "$(dirname "$0")" || exit 1
exec python3 -m creative_shell --dev "$@"
