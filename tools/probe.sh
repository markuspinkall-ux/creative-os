#!/bin/bash
# Ohne Anmeldung prüfen, ob die Container öffentlich ladbar sind
set +e
dnf install -y -q skopeo >/dev/null 2>&1
for img in creative-trellis creative-trellis2; do
  echo "== $img"
  skopeo inspect --no-creds --raw "docker://ghcr.io/markuspinkall-ux/$img:latest" 2>&1 | head -c 300; echo
done
exit 0
