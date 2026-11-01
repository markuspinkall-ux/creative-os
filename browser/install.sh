#!/bin/sh
# Brave im Creative-Look: eigene Startseite, Graphit-Farbe, ohne Werbe-Extras.
# (Für Firefox, solange Brave fehlt, nur die Startseite.)
set -eu
cd "$(dirname "$0")"

if [ "$(id -u)" -ne 0 ]; then
    echo "Bitte mit sudo ausführen: sudo ./install.sh"
    exit 1
fi

# Brave installieren, falls er fehlt (normales Fedora, z. B. in der Test-VM)
if ! command -v brave-browser >/dev/null 2>&1 && [ ! -e /run/ostree-booted ]; then
    echo "Brave wird installiert …"
    rpm --import https://brave-browser-rpm-release.s3.brave.com/brave-core.asc
    curl -fsSLo /etc/yum.repos.d/brave-browser.repo https://brave-browser-rpm-release.s3.brave.com/brave-browser.repo
    dnf install -y brave-browser
fi

rm -rf /usr/share/creative-os/startpage
mkdir -p /usr/share/creative-os/startpage
cp startpage/* /usr/share/creative-os/startpage/
chmod 644 /usr/share/creative-os/startpage/*

install -Dm644 brave-policies.json /etc/brave/policies/managed/creative-os.json
install -Dm644 firefox-policies.json /etc/firefox/policies/policies.json

# Startmenü neu aufräumen: mit Brave wird Firefox ausgeblendet
command -v creative-apps-sync >/dev/null 2>&1 && creative-apps-sync >/dev/null || true

echo "Fertig. Brave bitte einmal ganz schließen und neu öffnen."
