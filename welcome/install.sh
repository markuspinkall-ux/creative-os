#!/bin/sh
# Installiert den Willkommens-Assistenten (setzt Shell und Systemsteuerung voraus).
set -eu
cd "$(dirname "$0")"
if [ "$(id -u)" -ne 0 ]; then
    echo "Bitte mit sudo ausführen: sudo ./install.sh"
    exit 1
fi
rm -rf /usr/lib/creative-welcome
mkdir -p /usr/lib/creative-welcome
cp -r creative_welcome /usr/lib/creative-welcome/
find /usr/lib/creative-welcome -name '__pycache__' -prune -exec rm -rf {} +
install -Dm755 bin/creative-welcome /usr/bin/creative-welcome
echo "Fertig. Zum Ausprobieren: creative-welcome --force"
