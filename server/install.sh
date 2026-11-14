#!/bin/sh
# Installiert „Mein Server“ (Webserver Caddy + PHP). Eingeschaltet wird er in
# der Systemsteuerung › Mein Server.
set -eu
cd "$(dirname "$0")"

if [ "$(id -u)" -ne 0 ]; then
    echo "Bitte mit sudo ausführen: sudo ./install.sh"
    exit 1
fi

dnf install -y --skip-unavailable caddy php-fpm php-cli policycoreutils firewalld nss-mdns avahi

install -Dm755 creative-server-helper /usr/libexec/creative-server-helper
install -Dm644 creative-server.service /usr/lib/systemd/system/creative-server.service
install -Dm644 org.creativeos.server.policy /usr/share/polkit-1/actions/org.creativeos.server.policy
install -Dm755 creative-servermode /usr/libexec/creative-servermode
install -Dm644 creative-servermode.service /usr/lib/systemd/system/creative-servermode.service
install -Dm644 creative-servermode-reset.service /usr/lib/systemd/system/creative-servermode-reset.service
install -Dm644 org.creativeos.servermode.policy /usr/share/polkit-1/actions/org.creativeos.servermode.policy
install -Dm644 README.md /usr/share/doc/creative-server/README.md
systemctl daemon-reload
systemctl enable creative-servermode-reset.service 2>/dev/null || true
# Heimnetz-Name (z. B. http://mein-pc.local) bekannt machen
systemctl enable --now avahi-daemon.service 2>/dev/null || true

echo "Fertig. Einschalten: Systemsteuerung › Mein Server."
