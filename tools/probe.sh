#!/bin/bash
# Schnelle Prüfungen in einem frischen Fedora (Werkzeug für die Entwicklung)
set +e
dnf install -y -q obs-studio >/dev/null 2>&1; rpm -q obs-studio
ls /usr/share/obs/obs-studio/themes/
echo "=== Yami.obt"; cat /usr/share/obs/obs-studio/themes/Yami.obt | head -150
echo "=== Varianten"; for f in /usr/share/obs/obs-studio/themes/*.ovt; do echo "--- $f"; head -40 "$f"; done
obs --version 2>/dev/null
