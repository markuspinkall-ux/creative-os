#!/bin/sh
# Echte KWin-Vorschau: maximiertes Fenster ohne (gap=0) und mit Creative Abstand.
#   docker run --rm -v "$PWD:/src" -w /src registry.fedoraproject.org/fedora:44 sh tools/abstand-vorschau/vorschau.sh
set -eu
dnf -y -q install kwin-wayland python3-pyside6 python3-dbus dbus-daemon plasma-breeze layer-shell-qt \
    liberation-sans-fonts mesa-dri-drivers qt6-qtwayland qt6-qtdeclarative qt6-qtsvg \
    weston >/dev/null
cp /usr/bin/kwin_wayland /tmp/kwin_wayland        # ohne Datei-Capabilities (Container)
mkdir -p /src/fotos
for gap in ${GAPS:-0 6}; do
    export XDG_RUNTIME_DIR=/tmp/xdg-$gap XDG_CONFIG_HOME=/tmp/cfg-$gap XDG_DATA_HOME=/tmp/data-$gap
    mkdir -p -m 700 "$XDG_RUNTIME_DIR"; mkdir -p "$XDG_CONFIG_HOME" "$XDG_DATA_HOME/kwin/scripts"
    cp -r shell/kwin/creative-abstand "$XDG_DATA_HOME/kwin/scripts/"
    cp theme/kdeglobals theme/breezerc "$XDG_CONFIG_HOME/"
    sed 's/^creative-tasksEnabled=true//; s/^\[org.kde.kdecoration2\]$/[org.kde.kdecoration2]\nlibrary=org.kde.breeze\ntheme=Breeze/' \
        shell/kwin/kwinrc > "$XDG_CONFIG_HOME/kwinrc"
    printf '\n[Script-creative-abstand]\ngap=%s\n' "$gap" >> "$XDG_CONFIG_HOME/kwinrc"
    GAP=$gap timeout 90 dbus-run-session -- sh -c '
      # KWin läuft als Vollbild-Fenster in einem unsichtbaren Weston (Kiosk) – Weston kann fotografieren
      weston --backend=headless --renderer=pixman --shell=kiosk --width=1600 --height=1000 --socket=wl-host --debug >/tmp/weston-$GAP.log 2>&1 &
      sleep 3
      WAYLAND_DISPLAY=wl-host KWIN_COMPOSE=Q /tmp/kwin_wayland --wayland-display wl-host --width 1600 --height 1000 \
          --no-lockscreen --no-global-shortcuts --socket wayland-5 >/tmp/kwin-$GAP.log 2>&1 &
      sleep 6
      export WAYLAND_DISPLAY=wayland-5 QT_QPA_PLATFORM=wayland QT_QUICK_BACKEND=software
      timeout 40 python3 tools/abstand-vorschau/zeigen.py szene >/tmp/szene-$GAP.log 2>&1 & sleep 3
      timeout 40 python3 tools/abstand-vorschau/zeigen.py fenster >/tmp/fenster-$GAP.log 2>&1 & sleep 6
      (cd /tmp && rm -f wayland-screenshot*.png && WAYLAND_DISPLAY=wl-host weston-screenshooter && cp wayland-screenshot*.png /src/fotos/abstand-gap$GAP.png) || echo "kein Foto"
      echo "--- weston"; tail -8 /tmp/weston-$GAP.log
      echo "--- kwin"; tail -25 /tmp/kwin-$GAP.log; echo "--- szene"; tail -15 /tmp/szene-$GAP.log; echo "--- fenster"; tail -15 /tmp/fenster-$GAP.log
      kill $(jobs -p) 2>/dev/null; true
    ' || true
done
ls -la /src/fotos
