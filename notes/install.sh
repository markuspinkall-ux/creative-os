#!/bin/sh
# Installiert Creative Notes (setzt die Creative Shell voraus – sie liefert die Symbole).
set -eu
cd "$(dirname "$0")"
if [ "$(id -u)" -ne 0 ]; then
    echo "Bitte mit sudo ausführen: sudo ./install.sh"
    exit 1
fi
dnf install -y --skip-unavailable python3-pyside6 qt6-qtsvg liberation-mono-fonts qt6-qttranslations
rm -rf /usr/lib/creative-notes
mkdir -p /usr/lib/creative-notes
cp -r creative_notes /usr/lib/creative-notes/
find /usr/lib/creative-notes -name '__pycache__' -prune -exec rm -rf {} +
install -Dm755 bin/creative-notes /usr/bin/creative-notes
install -Dm644 creative-notes.desktop /usr/share/applications/creative-notes.desktop
update-desktop-database -q /usr/share/applications 2>/dev/null || true
echo "Fertig. „Creative Notes“ steht jetzt im Startmenü."
