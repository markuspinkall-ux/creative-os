#!/bin/sh
# Installiert den Creative Player auf einem bestehenden Fedora
# (setzt die Creative Shell voraus – sie liefert das gemeinsame Design).
set -eu
cd "$(dirname "$0")"

if [ "$(id -u)" -ne 0 ]; then
    echo "Bitte mit sudo ausführen: sudo ./install.sh"
    exit 1
fi

dnf install -y python3-pyside6 qt6-qtmultimedia qt6-qtsvg python3-mutagen
dnf install -y --skip-unavailable qt6-qtwebengine python3-pyside6-webengine || true

rm -rf /usr/lib/creative-media
mkdir -p /usr/lib/creative-media
cp -r creative_media /usr/lib/creative-media/
find /usr/lib/creative-media -name '__pycache__' -prune -exec rm -rf {} +
install -Dm755 bin/creative-player /usr/bin/creative-player
install -Dm644 creative-player.desktop /usr/share/applications/creative-player.desktop
install -Dm644 creative-player.svg /usr/share/icons/hicolor/scalable/apps/creative-player.svg
gtk-update-icon-cache -q /usr/share/icons/hicolor 2>/dev/null || true
update-desktop-database -q /usr/share/applications 2>/dev/null || true

echo "Fertig. „Creative Player“ steht jetzt im Startmenü."
