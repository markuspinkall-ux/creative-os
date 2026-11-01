#!/bin/sh
# Installiert „Dateien“ auf einem bestehenden Fedora
# (setzt die Creative Shell voraus – sie liefert das gemeinsame Design).
set -eu
cd "$(dirname "$0")"

if [ "$(id -u)" -ne 0 ]; then
    echo "Bitte mit sudo ausführen: sudo ./install.sh"
    exit 1
fi

dnf install -y --skip-unavailable python3-pyside6 qt6-qtsvg glib2 udisks2 util-linux xdg-user-dirs

rm -rf /usr/lib/creative-files
mkdir -p /usr/lib/creative-files
cp -r creative_files /usr/lib/creative-files/
find /usr/lib/creative-files -name '__pycache__' -prune -exec rm -rf {} +
install -Dm755 bin/creative-files /usr/bin/creative-files
install -Dm644 creative-files.desktop /usr/share/applications/creative-files.desktop
install -Dm644 creative-files.svg /usr/share/icons/hicolor/scalable/apps/creative-files.svg
gtk-update-icon-cache -q /usr/share/icons/hicolor 2>/dev/null || true

# In der Creative-OS-Sitzung öffnen Ordner immer mit „Dateien“
target=/usr/share/creative-os/xdg/creative-mimeapps.list
mkdir -p "$(dirname "$target")"
[ -f "$target" ] || echo "[Default Applications]" > "$target"
grep -q '^inode/directory=' "$target" || echo "inode/directory=creative-files.desktop" >> "$target"
update-desktop-database -q /usr/share/applications 2>/dev/null || true

echo "Fertig. „Dateien“ steht jetzt im Startmenü und in der Taskleiste."
