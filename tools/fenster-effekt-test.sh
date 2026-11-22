#!/bin/sh
# KWin-Effekt „gibeon-fenster“ in echtem KWin prüfen (Fedora-Container, virtueller Bildschirm):
# lädt er, laufen Öffnen/Minimieren/Wiederherstellen/Schließen ohne Skriptfehler durch?
#   docker run --rm -v "$PWD:/src" -w /src registry.fedoraproject.org/fedora:44 sh tools/fenster-effekt-test.sh
set -eu
dnf -y -q install kwin-wayland python3-pyside6 dbus-daemon dbus-tools plasma-breeze mesa-dri-drivers qt6-qtwayland kf6-kconfig >/dev/null
export XDG_RUNTIME_DIR=/tmp/xdg XDG_CONFIG_HOME=/tmp/cfg XDG_DATA_HOME=/tmp/data
mkdir -p -m 700 "$XDG_RUNTIME_DIR"; mkdir -p "$XDG_CONFIG_HOME" "$XDG_DATA_HOME/kwin/effects"
cp -r shell/kwin/gibeon-fenster "$XDG_DATA_HOME/kwin/effects/"
cp shell/kwin/kwinrc "$XDG_CONFIG_HOME/kwinrc"
cp /usr/bin/kwin_wayland /tmp/kwin_wayland
cat > /tmp/fenster.py <<'PY'
import sys, time
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QApplication, QWidget
app = QApplication(sys.argv)
app.setDesktopFileName("org.kde.dolphin")
w = QWidget(); w.resize(500, 350); w.show()
steps = [lambda: w.showMinimized(), lambda: w.showNormal(), lambda: w.close(), lambda: app.quit()]
for i, f in enumerate(steps):
    QTimer.singleShot(1500 * (i + 1), f)
app.exec()
PY
dbus-run-session -- sh -c '
  /tmp/kwin_wayland --virtual --width 1600 --height 1000 --no-lockscreen --no-global-shortcuts --socket wayland-7 >/tmp/kwin.log 2>&1 &
  sleep 5
  # wie die Shell: Symbol-Lage eintragen und den Effekt neu laden
  kwriteconfig6 --file kwinrc --group Effect-gibeon-fenster --key Tasten "[{\"n\":[\"org.kde.dolphin\",\"dolphin\"],\"x\":300,\"y\":975}]"
  kwriteconfig6 --file kwinrc --group Effect-gibeon-fenster --key Start "40,900,$(date +%s)000"
  dbus-send --session --print-reply --dest=org.kde.KWin /Effects org.kde.kwin.Effects.reconfigureEffect string:gibeon-fenster || true
  WAYLAND_DISPLAY=wayland-7 QT_QPA_PLATFORM=wayland timeout 30 python3 /tmp/fenster.py || true
  dbus-send --session --print-reply --dest=org.kde.KWin /Effects org.freedesktop.DBus.Properties.Get string:org.kde.kwin.Effects string:loadedEffects > /tmp/geladen.txt 2>&1 || true
' || true
tail -20 /tmp/kwin.log
cat /tmp/geladen.txt
if grep -iE "gibeon-fenster.*(error|TypeError|ReferenceError)|(TypeError|ReferenceError|SyntaxError)" /tmp/kwin.log; then
    echo "FEHLER im Effekt"; exit 1
fi
grep -q '"gibeon-fenster"' /tmp/geladen.txt || { echo "Effekt gibeon-fenster ist nicht geladen"; exit 1; }
echo "Fenster-Effekt: geladen, ohne Fehler"
