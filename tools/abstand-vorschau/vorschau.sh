#!/bin/sh
# Echte KWin-Vorschau: maximiertes Fenster ohne (gap=0) und mit Creative Abstand.
#   docker run --rm -v "$PWD:/src" -w /src registry.fedoraproject.org/fedora:44 sh tools/abstand-vorschau/vorschau.sh
set -eu
dnf -y -q install kwin-wayland python3-pyside6 python3-dbus dbus-daemon plasma-breeze layer-shell-qt \
    liberation-sans-fonts mesa-dri-drivers qt6-qtwayland qt6-qtdeclarative qt6-qtsvg >/dev/null
cp /usr/bin/kwin_wayland /tmp/kwin_wayland        # ohne Datei-Capabilities (Container)
mkdir -p /src/fotos
for gap in 0 6; do
    export XDG_RUNTIME_DIR=/tmp/xdg-$gap XDG_CONFIG_HOME=/tmp/cfg-$gap XDG_DATA_HOME=/tmp/data-$gap
    mkdir -p -m 700 "$XDG_RUNTIME_DIR"; mkdir -p "$XDG_CONFIG_HOME" "$XDG_DATA_HOME/kwin/scripts"
    cp -r shell/kwin/creative-abstand "$XDG_DATA_HOME/kwin/scripts/"
    cp theme/kdeglobals theme/breezerc "$XDG_CONFIG_HOME/"
    sed 's/^creative-tasksEnabled=true//; s/^\[org.kde.kdecoration2\]$/[org.kde.kdecoration2]\nlibrary=org.kde.breeze\ntheme=Breeze/' \
        shell/kwin/kwinrc > "$XDG_CONFIG_HOME/kwinrc"
    printf '\n[Script-creative-abstand]\ngap=%s\n' "$gap" >> "$XDG_CONFIG_HOME/kwinrc"
    GAP=$gap dbus-run-session -- sh -c '
      KWIN_SCREENSHOT_NO_PERMISSION_CHECKS=1 /tmp/kwin_wayland --virtual --width 1600 --height 1000 \
          --no-lockscreen --no-global-shortcuts --socket wayland-5 >/tmp/kwin-$GAP.log 2>&1 &
      sleep 5
      export WAYLAND_DISPLAY=wayland-5 QT_QPA_PLATFORM=wayland
      python3 tools/abstand-vorschau/zeigen.py szene & sleep 3
      python3 tools/abstand-vorschau/zeigen.py fenster & sleep 6
      python3 tools/abstand-vorschau/foto.py /src/fotos/abstand-gap$GAP.png || tail -20 /tmp/kwin-$GAP.log
    ' || true
done
ls -la /src/fotos
