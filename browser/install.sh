#!/bin/sh
# Startseite des Creative Browsers installieren (Brave ist nicht mehr Teil von Orbit OS).
# (Für Firefox, falls installiert, dieselbe Startseite.)
set -eu
cd "$(dirname "$0")"

if [ "$(id -u)" -ne 0 ]; then
    echo "Bitte mit sudo ausführen: sudo ./install.sh"
    exit 1
fi

rm -rf /usr/share/creative-os/startpage
mkdir -p /usr/share/creative-os/startpage
cp startpage/* /usr/share/creative-os/startpage/
chmod 644 /usr/share/creative-os/startpage/*

install -Dm644 firefox-policies.json /etc/firefox/policies/policies.json

command -v creative-apps-sync >/dev/null 2>&1 && creative-apps-sync >/dev/null || true
echo "Fertig."
