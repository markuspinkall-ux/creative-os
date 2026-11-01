#!/bin/sh
# Installiert Creative Pictures (setzt die Creative Shell voraus).
set -eu
cd "$(dirname "$0")"
if [ "$(id -u)" -ne 0 ]; then
    echo "Bitte mit sudo ausführen: sudo ./install.sh"
    exit 1
fi
dnf install -y --skip-unavailable python3-pillow qt6-qtimageformats kf6-kimageformats
rm -rf /usr/lib/creative-pictures
mkdir -p /usr/lib/creative-pictures
cp -r creative_pictures /usr/lib/creative-pictures/
find /usr/lib/creative-pictures -name '__pycache__' -prune -exec rm -rf {} +
install -Dm755 bin/creative-pictures /usr/bin/creative-pictures
install -Dm644 creative-pictures.desktop /usr/share/applications/creative-pictures.desktop
update-desktop-database -q /usr/share/applications 2>/dev/null || true
echo "Fertig. „Creative Pictures“ steht jetzt im Startmenü."
