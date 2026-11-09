#!/bin/sh
# Installiert die Creative Shell auf einem bestehenden Fedora-System
# (Vorstufe zum späteren RPM-Paket). Mit sudo ausführen.
set -eu
cd "$(dirname "$0")"

if [ "$(id -u)" -ne 0 ]; then
    echo "Bitte mit sudo ausführen: sudo ./install.sh"
    exit 1
fi

echo "Installiere benötigte Pakete …"
dnf install -y --skip-unavailable \
    python3-pyside6 qt6-qtsvg qt6-qtwayland layer-shell-qt \
    kwin-wayland \
    NetworkManager cups brightnessctl ddcutil glib2 \
    liberation-sans-fonts

echo "Kopiere Dateien …"
rm -rf /usr/lib/creative-shell
mkdir -p /usr/lib/creative-shell
cp -r creative_shell /usr/lib/creative-shell/
find /usr/lib/creative-shell -name '__pycache__' -prune -exec rm -rf {} +

install -Dm755 bin/creative-shell /usr/bin/creative-shell
install -Dm755 session/creative-session /usr/bin/creative-session
install -Dm755 session/creative-shell-supervisor /usr/libexec/creative-shell-supervisor
install -Dm644 session/creative.desktop /usr/share/wayland-sessions/creative.desktop
install -Dm644 kwin/kwinrc /usr/share/creative-os/xdg/kwinrc
install -Dm644 kwin/kscreenlockerrc /usr/share/creative-os/xdg/kscreenlockerrc
install -Dm644 kwin/kxkbrc /usr/share/creative-os/xdg/kxkbrc
sh lockscreen/install-lockscreen.sh
rm -rf /usr/share/kwin/scripts/creative-tasks
mkdir -p /usr/share/kwin/scripts
cp -r kwin/creative-tasks /usr/share/kwin/scripts/

# Web-Apps als eigene Fenster (Claude, YouTube, Twitch); ChatGPT startet die offizielle App von OpenAI
install -Dm755 webapps/creative-webapp /usr/bin/creative-webapp
for app in claude chatgpt youtube twitch; do
    install -Dm644 "webapps/creative-$app.desktop" "/usr/share/applications/creative-$app.desktop"
    install -Dm644 "creative_shell/qml/Creative/icons/$app.svg" "/usr/share/icons/hicolor/scalable/apps/creative-$app.svg"
done
gtk-update-icon-cache -q /usr/share/icons/hicolor 2>/dev/null || true

# Helligkeit externer Monitore (DDC/CI) ohne Root-Rechte erlauben
if getent group i2c >/dev/null 2>&1 && [ -n "${SUDO_USER:-}" ]; then
    usermod -aG i2c "$SUDO_USER"
fi

echo
echo "Fertig. Abmelden und im Anmeldebildschirm die Sitzung „Creative OS“ wählen."
