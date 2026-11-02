#!/bin/bash
set +e
dnf install -y -q python3-pyside6 qt6-qtdeclarative qt6-qtsvg qt6-qtmultimedia python3-psutil python3-numpy liberation-sans-fonts google-noto-sans-fonts xdg-user-dirs >/dev/null 2>&1
export QT_QPA_PLATFORM=offscreen XDG_RUNTIME_DIR=/tmp/rt HOME=/tmp/h QT_QUICK_BACKEND=software
mkdir -p /tmp/rt /tmp/h/Schreibtisch/Projekte; chmod 700 /tmp/rt
echo hallo > /tmp/h/Schreibtisch/notiz.txt; touch /tmp/h/Schreibtisch/Bild.png /tmp/h/Schreibtisch/Rechnung.pdf
PYTHONPATH=shell timeout 60 python3 tools/wallshot.py /tmp/wall.png 2>&1 | grep -v "^qt\.\|Fontconfig" | tail -15
[ -f /tmp/wall.png ] && { echo BILD-ANFANG; base64 /tmp/wall.png | sed "s/^/B64wall:/"; echo BILD-ENDE; }
exit 0
