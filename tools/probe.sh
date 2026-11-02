#!/bin/bash
# Creative Shell in einem virtuellen KWin starten und Fehler mitschneiden
set +e
dnf install -y -q kwin layer-shell-qt python3-pyside6 qt6-qtdeclarative qt6-qtsvg qt6-qtmultimedia python3-psutil python3-numpy dbus-daemon dbus-x11 liberation-sans-fonts xdg-user-dirs glib2 >/dev/null 2>&1
rpm -q kwin layer-shell-qt python3-pyside6 | tail -3
export XDG_RUNTIME_DIR=/tmp/rt HOME=/tmp/h QT_QPA_PLATFORM=wayland
mkdir -p /tmp/rt /tmp/h/Schreibtisch; chmod 700 /tmp/rt
touch /tmp/h/Schreibtisch/test.txt
cp "$(command -v kwin_wayland)" /tmp/kwin_wayland_nocap; chmod 755 /tmp/kwin_wayland_nocap
for kb in neu; do
  if [ "$kb" = alt ]; then sed -i 's/geo.width(), geo.height(), True)/geo.width(), geo.height(), False)/' shell/creative_shell/__main__.py; fi
  echo "=== Variante $kb: $(grep -o 'geo.height(), [A-Za-z]*)' shell/creative_shell/__main__.py | head -1)"
  cat > /tmp/run.sh <<'S'
#!/bin/sh
cd /__w/creative-os/creative-os/shell 2>/dev/null || cd "$GITHUB_WORKSPACE/shell"
PYTHONPATH=. timeout 20 python3 -m creative_shell 2>&1 | grep -v "^qt.qpa\|Fontconfig" | head -40
echo "Shell-Ende: Code $?"
S
  chmod +x /tmp/run.sh
  timeout 40 dbus-run-session -- /tmp/kwin_wayland_nocap --virtual --width 1280 --height 800 --no-lockscreen --exit-with-session /tmp/run.sh 2>&1 \
     | grep -v "Fontconfig\|libinput" | tail -60
done
exit 0
