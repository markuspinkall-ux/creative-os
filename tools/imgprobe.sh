#!/bin/bash
# Prüfungen im fertigen Abbild (läuft auf GitHub, zieht das Test-Abbild)
set +e
img=ghcr.io/markuspinkall-ux/creative-os:amd-testing
sudo podman pull -q "$img" >/dev/null
sudo podman run --rm "$img" sh -c '
echo "=== Dateien mit fedora im Namen (Bilder/Symbole/Designs)"
find /usr/share -xdev \( -iname "*fedora*" \) \( -name "*.png" -o -name "*.svg" -o -name "*.jpg" -o -name "*.webp" -o -name "*.desktop" -o -name "*.qml" \) 2>/dev/null | grep -v "/doc/\|/licenses/" | head -80
echo "=== system-logo"; find /usr/share -iname "system-logo*" | head
echo "=== rpm fedora-logos"; rpm -q fedora-logos generic-logos; rpm -q --whatrequires fedora-logos system-logos | head
echo "=== Plasma-Erscheinungsbilder"; ls /usr/share/plasma/look-and-feel/ 2>/dev/null
echo "=== Hintergründe"; ls /usr/share/wallpapers/ /usr/share/backgrounds/ 2>/dev/null | head -30
echo "=== efi"; ls /usr/lib/bootupd/updates/EFI/ 2>/dev/null; ls /boot/efi/EFI 2>/dev/null
'
