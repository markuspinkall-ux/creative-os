#!/bin/bash
# Creative OS – Gesundheitsprüfung nach dem Start (greenboot, „required“):
# Kommt der Anmeldebildschirm hoch und sind die eigenen Bausteine vollständig?
# Schlägt das fehl, rollt Creative OS auf die vorige Version zurück (red.d).
set -u
# Nur ein eindeutiger Fehler zählt (Dienst „failed“) – dauert der Start nur länger,
# wird nicht zurückgerollt.
for i in $(seq 1 90); do
    systemctl is-active --quiet display-manager.service && break
    if systemctl is-failed --quiet display-manager.service; then
        echo "Creative OS: Anmeldebildschirm startet nicht" >&2
        exit 1
    fi
    sleep 2
done
for f in /usr/bin/creative-shell /usr/bin/kwin_wayland /usr/bin/creative-settings; do
    [ -x "$f" ] || { echo "Creative OS: $f fehlt" >&2; exit 1; }
done
# Taskleiste: Python-Teil lässt sich laden
python3 -c "import sys; sys.path.insert(0, '/usr/lib/creative-shell'); import creative_shell.config, creative_shell.tasks" \
    || { echo "Creative OS: Taskleiste ist beschädigt" >&2; exit 1; }
exit 0
