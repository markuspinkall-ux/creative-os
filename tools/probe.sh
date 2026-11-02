#!/bin/bash
# Bildschirmfotos von Creative Iso und Creative Capture (ohne Bildschirm gerendert)
set +e
dnf install -y -q python3-pyside6 qt6-qtmultimedia qt6-qtdeclarative qt6-qtsvg liberation-sans-fonts liberation-fonts-all google-noto-sans-fonts mesa-dri-drivers xdg-user-dirs >/dev/null 2>&1
rpm -q python3-pyside6
export QT_QPA_PLATFORM=offscreen XDG_RUNTIME_DIR=/tmp/rt HOME=/tmp/h QT_QUICK_BACKEND=software
mkdir -p /tmp/rt /tmp/h; chmod 700 /tmp/rt
for app in iso:creative_iso capture:creative_capture; do
  dir=${app%%:*}; mod=${app#*:}
  (cd $dir && PYTHONPATH=. timeout 60 python3 ../tools/shot.py $mod /tmp/$dir.png 3500) 2>&1 | grep -v "^qt.\|Fontconfig" | tail -5
  [ -f /tmp/$dir.png ] && { echo "BILD-$dir-ANFANG"; base64 /tmp/$dir.png | sed "s/^/B64$dir:/"; echo "BILD-$dir-ENDE"; }
done
