#!/bin/sh
# Wayland-App-Kennung (app_id) von Browser, WhatsApp und Web-App in echtem KWin prüfen –
# die Taskleiste gruppiert danach. Läuft in Fedora 44 (Container), Electron wie im Abbild verpackt.
#   docker run --rm -v "$PWD:/src" -w /src registry.fedoraproject.org/fedora:44 sh tools/appid-test/appid-test.sh
set -eu
ELECTRON_VERSION="${ELECTRON_VERSION:-45.3.1}"
dnf -y -q install kwin-wayland dbus-daemon nodejs npm unzip gtk3 nss alsa-lib libxkbcommon mesa-libgbm libdrm \
    cups-libs at-spi2-atk mesa-dri-drivers liberation-sans-fonts >/dev/null
cp /usr/bin/kwin_wayland /tmp/kwin_wayland
mkdir -p /tmp/pkg && cd /tmp && npm init -y >/dev/null && npm install --no-audit --no-fund --foreground-scripts "electron@${ELECTRON_VERSION}" >/dev/null
[ -x /tmp/node_modules/electron/dist/electron ] || node /tmp/node_modules/electron/install.js
ls /tmp/node_modules/electron/dist | head -3
cp -a /tmp/node_modules/electron/dist/. /tmp/pkg/ && rm -f /tmp/pkg/resources/default_app.asar
cp -a /src/webbrowser/app /tmp/pkg/resources/app
(cd /tmp/pkg/resources/app && npm ci --omit=dev --no-audit --no-fund --ignore-scripts >/dev/null)
mkdir -p /tmp/browser && cp -a /src/browser/startpage /tmp/browser/startpage
cd /src
export XDG_RUNTIME_DIR=/tmp/xdg XDG_CONFIG_HOME=/tmp/cfg XDG_DATA_HOME=/tmp/data HOME=/tmp/home
mkdir -p -m 700 "$XDG_RUNTIME_DIR"; mkdir -p "$XDG_CONFIG_HOME" "$XDG_DATA_HOME/kwin/scripts" "$HOME"
cp -r tools/appid-test/fensterliste "$XDG_DATA_HOME/kwin/scripts/"
printf '[Plugins]\nfensterlisteEnabled=true\n' > "$XDG_CONFIG_HOME/kwinrc"
dbus-run-session -- sh -c '
  QT_FORCE_STDERR_LOGGING=1 QT_LOGGING_RULES="kwin_scripting.debug=true;js.debug=true;qml.debug=true" /tmp/kwin_wayland --virtual --width 1600 --height 1000 --no-lockscreen --no-global-shortcuts --socket wayland-6 >/tmp/kwin.log 2>&1 &
  sleep 5
  export WAYLAND_DISPLAY=wayland-6
  E="/tmp/pkg/electron --no-sandbox --ozone-platform=wayland --disable-gpu"
  CHROME_DESKTOP=creative-whatsapp.desktop timeout 60 $E --class=creative-whatsapp --whatsapp >/tmp/w.log 2>&1 &
  sleep 4
  CHROME_DESKTOP=creative-browser.desktop timeout 50 $E --class=creative-browser about:blank >/tmp/b.log 2>&1 &
  sleep 4
  timeout 40 $E --class=creative-claude --app=https://example.org/ --app-name=claude >/tmp/c.log 2>&1 &
  for i in $(seq 1 40); do
    grep -q "FENSTER app=creative-whatsapp\|FENSTER app=creative-browser class=creative-whatsapp" /tmp/kwin.log && break
    sleep 1
  done
  sleep 3
' || true
echo "--- KWin sieht:"; grep "FENSTER" /tmp/kwin.log | sort -u || true
grep -q FENSTER /tmp/kwin.log || { echo "--- kwin.log"; tail -30 /tmp/kwin.log; echo "--- browser"; tail -15 /tmp/b.log; }
grep -q "FENSTER app=creative-browser" /tmp/kwin.log || { echo "FEHLER: Browserfenster fehlt"; tail -20 /tmp/b.log; exit 1; }
grep -q "FENSTER app=creative-whatsapp" /tmp/kwin.log || { echo "FEHLER: WhatsApp hat keine eigene Kennung"; tail -20 /tmp/w.log; exit 1; }
grep -q "FENSTER app=creative-claude" /tmp/kwin.log || { echo "FEHLER: Web-App Claude hat keine eigene Kennung"; tail -20 /tmp/c.log; exit 1; }
echo "Eigene Taskleisten-Einträge: Browser, WhatsApp und Claude haben getrennte Kennungen"
