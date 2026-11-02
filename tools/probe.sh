#!/bin/bash
set +e
dnf install -y -q python3-pyside6 qt6-qtdeclarative qt6-qtsvg layer-shell-qt python3-dbus python3-gobject dbus-daemon glib2 liberation-sans-fonts google-noto-sans-fonts breeze-icon-theme >/dev/null 2>&1
export QT_QPA_PLATFORM=offscreen XDG_RUNTIME_DIR=/tmp/rt HOME=/tmp/h QT_QUICK_BACKEND=software
mkdir -p /tmp/rt /tmp/h; chmod 700 /tmp/rt
PYTHONPATH=notify:shell timeout 60 dbus-run-session -- python3 tools/notifytest.py 2>&1 | grep -v "^qt\.\|Fontconfig" | tail -15
[ -f /tmp/notify.png ] && { echo BILD-ANFANG; base64 /tmp/notify.png | sed "s/^/B64n:/"; echo BILD-ENDE; }
exit 0
