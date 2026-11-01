#!/bin/sh
# Installiert die Systemsteuerung (setzt die Creative Shell voraus).
set -eu
cd "$(dirname "$0")"

if [ "$(id -u)" -ne 0 ]; then
    echo "Bitte mit sudo ausführen: sudo ./install.sh"
    exit 1
fi

dnf install -y --skip-unavailable python3-pyside6 qt6-qtsvg libkscreen pipewire-utils pulseaudio-utils \
    cups-client pciutils polkit-kde system-config-printer

rm -rf /usr/lib/creative-settings
mkdir -p /usr/lib/creative-settings
cp -r creative_settings /usr/lib/creative-settings/
find /usr/lib/creative-settings -name '__pycache__' -prune -exec rm -rf {} +
install -Dm755 bin/creative-settings /usr/bin/creative-settings
install -Dm644 creative-settings.desktop /usr/share/applications/creative-settings.desktop
install -Dm644 ../shell/creative_shell/qml/Creative/icons/settings.svg /usr/share/icons/hicolor/scalable/apps/creative-settings.svg
gtk-update-icon-cache -q /usr/share/icons/hicolor 2>/dev/null || true
update-desktop-database -q /usr/share/applications 2>/dev/null || true
# Startmenü neu aufräumen (die KDE-Systemsteuerung wird jetzt ausgeblendet)
command -v creative-apps-sync >/dev/null 2>&1 && creative-apps-sync >/dev/null || true

echo "Fertig. Die Systemsteuerung öffnet sich mit Windows-Taste + I oder über das Startmenü."
