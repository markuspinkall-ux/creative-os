#!/bin/sh
# Installiert Creative Shots (setzt die Creative Shell voraus; Spectacle nimmt im Hintergrund auf).
set -eu
cd "$(dirname "$0")"
if [ "$(id -u)" -ne 0 ]; then
    echo "Bitte mit sudo ausführen: sudo ./install.sh"
    exit 1
fi
dnf install -y --skip-unavailable spectacle xdg-user-dirs
rm -rf /usr/lib/creative-shots
mkdir -p /usr/lib/creative-shots
cp -r creative_shots /usr/lib/creative-shots/
find /usr/lib/creative-shots -name '__pycache__' -prune -exec rm -rf {} +
install -Dm755 bin/creative-shots /usr/bin/creative-shots
install -Dm644 creative-shots.desktop /usr/share/applications/creative-shots.desktop
update-desktop-database -q /usr/share/applications 2>/dev/null || true
echo "Fertig. „Creative Shots“: Druck-Taste oder Win+Umschalt+S."
