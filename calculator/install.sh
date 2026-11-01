#!/bin/sh
# Installiert den Creative Calculator (setzt die Creative Shell voraus).
set -eu
cd "$(dirname "$0")"
if [ "$(id -u)" -ne 0 ]; then
    echo "Bitte mit sudo ausführen: sudo ./install.sh"
    exit 1
fi
rm -rf /usr/lib/creative-calculator
mkdir -p /usr/lib/creative-calculator
cp -r creative_calculator /usr/lib/creative-calculator/
find /usr/lib/creative-calculator -name '__pycache__' -prune -exec rm -rf {} +
install -Dm755 bin/creative-calculator /usr/bin/creative-calculator
install -Dm644 creative-calculator.desktop /usr/share/applications/creative-calculator.desktop
update-desktop-database -q /usr/share/applications 2>/dev/null || true
echo "Fertig. „Creative Calculator“ steht jetzt im Startmenü."
