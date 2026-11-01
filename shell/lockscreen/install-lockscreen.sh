#!/bin/sh
# Setzt den Creative-Graphit-Sperrbildschirm ein.
#
# Seit Plasma 6 liegt der Sperrbildschirm im Plasma-Shell-Paket. Das Original
# wird beim ersten Mal gesichert und lässt sich jederzeit zurückholen:
#   sudo ./install-lockscreen.sh --restore
set -eu
cd "$(dirname "$0")"

LS=/usr/share/plasma/shells/org.kde.plasma.desktop/contents/lockscreen
BACKUP="$LS.creative-backup"

if [ ! -d "$LS" ]; then
    echo "Sperrbildschirm-Ordner nicht gefunden: $LS"
    exit 1
fi

if [ "${1:-}" = "--restore" ]; then
    if [ -d "$BACKUP" ]; then
        rm -rf "$LS"
        cp -a "$BACKUP" "$LS"
        echo "Original-Sperrbildschirm wiederhergestellt."
    else
        echo "Keine Sicherung gefunden – nichts zu tun."
    fi
    exit 0
fi

[ -d "$BACKUP" ] || cp -a "$LS" "$BACKUP"
install -m644 LockScreen.qml "$LS/LockScreen.qml"
install -m644 graphit.svg "$LS/graphit.svg"
echo "Creative-Sperrbildschirm eingesetzt (Original gesichert unter $BACKUP)."
