#!/bin/sh
# Anmeldebildschirm im Graphit-Look (SDDM) – meldet direkt in Creative OS an.
#   sudo ./install.sh          installieren und als Anmeldebildschirm einschalten
#   sudo ./install.sh --test   nur ansehen (Fenster, ohne etwas umzustellen)
#   sudo ./install.sh --zurueck  wieder den vorherigen Anmeldebildschirm nutzen
set -eu
cd "$(dirname "$0")"
if [ "$(id -u)" -ne 0 ]; then
    echo "Bitte mit sudo ausführen: sudo ./install.sh"
    exit 1
fi

if [ "${1:-}" = "--zurueck" ]; then
    rm -f /etc/sddm.conf.d/10-creative.conf
    if systemctl list-unit-files plasmalogin.service >/dev/null 2>&1; then
        systemctl disable sddm.service 2>/dev/null || true
        systemctl enable --force plasmalogin.service
    fi
    echo "Zurückgestellt. Nach dem Neustart erscheint wieder der vorherige Anmeldebildschirm."
    exit 0
fi

[ "${SKIP_DNF:-0}" = 1 ] || dnf install -y --skip-unavailable sddm sddm-wayland-plasma
rm -rf /usr/share/sddm/themes/creative
mkdir -p /usr/share/sddm/themes
cp -r creative /usr/share/sddm/themes/creative

if [ "${1:-}" = "--test" ]; then
    greeter="$(command -v sddm-greeter-qt6 || command -v sddm-greeter)"
    sudo -u "${SUDO_USER:-$USER}" "$greeter" --test-mode --theme /usr/share/sddm/themes/creative
    exit 0
fi

install -Dm644 sddm-creative.conf /etc/sddm.conf.d/10-creative.conf
systemctl disable plasmalogin.service 2>/dev/null || true
systemctl enable --force sddm.service
echo "Fertig. Nach dem nächsten Neustart erscheint der Creative-Anmeldebildschirm."
echo "Zurück zum alten: sudo ./install.sh --zurueck"
