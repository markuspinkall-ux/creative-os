#!/bin/bash
# Creative OS (greenboot green.d): diese Version ist gesund gestartet – merken.
mkdir -p /var/lib/creative-os
rpm-ostree status --json 2>/dev/null | python3 -c "
import json, sys
d = json.load(sys.stdin)
b = next((x for x in d.get('deployments', []) if x.get('booted')), None)
print(b['checksum'] if b else '')" > /var/lib/creative-os/last-good.tmp \
  && [ -s /var/lib/creative-os/last-good.tmp ] && mv /var/lib/creative-os/last-good.tmp /var/lib/creative-os/last-good
rm -f /var/lib/creative-os/last-good.tmp
exit 0
