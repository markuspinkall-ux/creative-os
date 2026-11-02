#!/bin/bash
# Creative OS (greenboot red.d): Die neue Version startet nicht richtig →
# automatisch zur letzten gesunden Version zurück und neu starten.
# Nur wenn gerade eine NEUE Version läuft (sonst keine Neustart-Schleife).
set -u
good=$(cat /var/lib/creative-os/last-good 2>/dev/null || true)
cur=$(rpm-ostree status --json 2>/dev/null | python3 -c "
import json, sys
d = json.load(sys.stdin)
b = next((x for x in d.get('deployments', []) if x.get('booted')), None)
print(b['checksum'] if b else '')" 2>/dev/null)
if [ -z "$good" ] || [ -z "$cur" ] || [ "$cur" = "$good" ]; then
    echo "Creative OS: Prüfung fehlgeschlagen, aber keine neuere Version zum Zurückrollen" >&2
    exit 0
fi
echo "Creative OS: Neue Version startet nicht richtig – zurück zur letzten funktionierenden Version" >&2
mkdir -p /var/lib/creative-os
date '+%Y-%m-%d %H:%M' > /var/lib/creative-os/rolled-back
if rpm-ostree rollback; then
    systemctl reboot
fi
exit 0
