#!/bin/sh
# Nur Darstellung anpassen; KDE-Passwortprüfung und Entsperren bleiben original.
set -eu
cd "$(dirname "$0")"
LS=/usr/share/plasma/shells/org.kde.plasma.desktop/contents/lockscreen/LockScreenUi.qml
[ -f "$LS" ] || { echo "KDE-Sperrbildschirm nicht gefunden."; exit 1; }
if [ "${1:-}" = "--restore" ]; then
    [ ! -f "$LS.creative-original" ] || cp "$LS.creative-original" "$LS"
    exit 0
fi
python3 style-lockscreen.py "$LS"
echo "Creative-Graphit-Stil ergänzt; KDE-Entsperrmechanik beibehalten."
