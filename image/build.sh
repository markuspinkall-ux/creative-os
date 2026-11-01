#!/bin/sh
# Baut das Creative-OS-Abbild und daraus eine Installations-ISO.
# Läuft auf Fedora (z. B. in deiner VirtualBox-VM).
#
#   ./image/build.sh            NVIDIA-Variante
#   ./image/build.sh amd        Variante für AMD/Intel-Grafik
#
# Ergebnis: output/bootiso/install.iso
set -eu
cd "$(dirname "$0")/.."

variant="${1:-nvidia}"
case "$variant" in
    nvidia) nv=1 ;;
    amd|intel) nv=0; variant=amd ;;
    *) echo "Unbekannte Variante: $variant (nvidia oder amd)"; exit 1 ;;
esac
image="localhost/creative-os:${variant}"

echo "1/2  Baue System-Abbild ${image} …"
sudo podman build --layers=false --pull=newer -f image/Containerfile --build-arg NVIDIA="$nv" -t "$image" .

echo "2/2  Erzeuge Installations-ISO …"
mkdir -p output
sudo podman run --rm -it --privileged --pull=newer \
    --security-opt label=type:unconfined_t \
    -v ./output:/output \
    -v /var/lib/containers/storage:/var/lib/containers/storage \
    quay.io/centos-bootc/bootc-image-builder:latest \
    --type anaconda-iso --rootfs btrfs "$image"

echo
echo "Fertig: output/bootiso/install.iso"
