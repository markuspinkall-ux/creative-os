#!/bin/sh
# Maximieren in echtem KWin prüfen (ohne Abstand) (Fedora-Container, virtueller Bildschirm 1600×1000).
#   docker run --rm -v "$PWD:/src" -w /src registry.fedoraproject.org/fedora:44 sh tools/abstand-test.sh
set -eu
dnf -y -q install kwin-wayland python3-pyside6 dbus-daemon dbus-tools plasma-breeze mesa-dri-drivers qt6-qtwayland >/dev/null
export XDG_RUNTIME_DIR=/tmp/xdg XDG_CONFIG_HOME=/tmp/cfg XDG_DATA_HOME=/tmp/data
mkdir -p -m 700 "$XDG_RUNTIME_DIR"; mkdir -p "$XDG_CONFIG_HOME" "$XDG_DATA_HOME/kwin/scripts" /src/fotos
cp -r shell/kwin/creative-abstand shell/kwin/creative-tasks "$XDG_DATA_HOME/kwin/scripts/"
cp shell/kwin/kwinrc "$XDG_CONFIG_HOME/kwinrc"
printf '\n[Script-creative-abstand]\ngap=%s\n' "${GAP:-6}" >> "$XDG_CONFIG_HOME/kwinrc"
# kwin_wayland hat Datei-Capabilities, die im Container nicht erlaubt sind – Kopie ohne
cp /usr/bin/kwin_wayland /tmp/kwin_wayland
dbus-run-session -- sh -c '
  /tmp/kwin_wayland --virtual --width 1600 --height 1000 --output-count 2 --no-lockscreen --no-global-shortcuts --socket wayland-7 >/tmp/kwin.log 2>&1 &
  sleep 5
  WAYLAND_DISPLAY=wayland-7 QT_QPA_PLATFORM=wayland timeout 30 python3 tools/abstand-client.py /tmp/abstand.json || true
' || true
tail -15 /tmp/kwin.log
# Skriptfehler (z. B. in der Fensterplatzierung von creative-tasks) wären hier zu sehen
if grep -iE "creative-(tasks|abstand).*(error|TypeError|ReferenceError)|(TypeError|ReferenceError).*creative" /tmp/kwin.log; then
    echo "FEHLER im KWin-Skript"; exit 1
fi
python3 - <<'PY'
import json, os
r = {x["step"]: x for x in json.load(open("/tmp/abstand.json"))}
gap = int(os.environ.get("GAP", "6"))
n, m, b = r["normal"], r["maximiert"], r["wieder normal"]
print(n, m, b, sep="\n")
# creative-abstand ist abgeschaltet: maximiert heißt randlos über die ganze Fläche
assert m["maximized"], "Fenster ist nicht maximiert"
assert m["w"] >= 1600 - 4 and m["h"] >= 1000 - 60, "maximiertes Fenster füllt die Fläche nicht"
assert (b["w"], b["h"]) == (n["w"], n["h"]), "Wiederherstellen bringt die alte Größe nicht zurück"
print("Maximieren ohne Abstand: in Ordnung")
PY
