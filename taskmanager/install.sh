#!/bin/sh
# Installiert den Taskmanager (setzt die Creative Shell voraus).
set -eu
cd "$(dirname "$0")"
if [ "$(id -u)" -ne 0 ]; then
    echo "Bitte mit sudo ausführen: sudo ./install.sh"
    exit 1
fi
dnf install -y --skip-unavailable python3-psutil pciutils
rm -rf /usr/lib/creative-taskmanager
mkdir -p /usr/lib/creative-taskmanager
cp -r creative_taskmanager /usr/lib/creative-taskmanager/
find /usr/lib/creative-taskmanager -name '__pycache__' -prune -exec rm -rf {} +
install -Dm755 bin/creative-taskmanager /usr/bin/creative-taskmanager
install -Dm644 creative-taskmanager.desktop /usr/share/applications/creative-taskmanager.desktop
update-desktop-database -q /usr/share/applications 2>/dev/null || true
echo "Fertig. „Taskmanager“ steht jetzt im Startmenü (Strg+Umschalt+Esc)."
