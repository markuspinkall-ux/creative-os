#!/bin/bash
# Macht aus der Fedora-Netzinstallation die Creative-OS-Installation:
#  - Installer-Name „Creative OS“ (über ein updates.img mit eigener .buildstamp)
#  - Einträge im Startmenü der ISO: „Install Creative OS“ statt „Install Fedora 44“
# Aufruf: brand-iso.sh <netinst.iso> <kickstart> <ziel.iso>
set -euo pipefail
src="$1"; ks="$2"; out="$3"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

# 1) updates.img mit eigenem Produktnamen
mkdir -p "$work/upd"
cat > "$work/upd/.buildstamp" <<STAMP
[Main]
Product=Creative OS
Version=$(date +%Y.%m)
BugURL=https://github.com/markuspinkall-ux/creative-os/issues
IsFinal=True
UUID=$(date +%Y%m%d%H%M).x86_64
Variant=Everything

[Compose]
Lorax=creative-os
STAMP
(cd "$work/upd" && find . | cpio -o -H newc --quiet | gzip -9) > "$work/updates.img"

# 2) Kickstart + updates.img einbauen
mkksiso --ks "$ks" --updates "$work/updates.img" "$src" "$work/stage1.iso"

# 3) Menüeinträge umbenennen (BIOS-, UEFI-Menü und das UEFI-Startabbild)
brand() { sed -i -E '/menuentry|menu label|^\s*label/ s/Fedora( Linux)?( [0-9]+)?/Creative OS/g' "$1"; }
args=()
for f in /EFI/BOOT/grub.cfg /boot/grub2/grub.cfg /isolinux/isolinux.cfg; do
    local_f="$work/$(echo "$f" | tr '/' '_')"
    if xorriso -osirrox on -indev "$work/stage1.iso" -extract "$f" "$local_f" >/dev/null 2>&1; then
        chmod u+w "$local_f"; brand "$local_f"; args+=(-update "$local_f" "$f")
    fi
done
if xorriso -osirrox on -indev "$work/stage1.iso" -extract /images/efiboot.img "$work/efiboot.img" >/dev/null 2>&1; then
    chmod u+w "$work/efiboot.img"
    if mtype -i "$work/efiboot.img" ::/EFI/BOOT/grub.cfg > "$work/efi-grub.cfg" 2>/dev/null; then
        brand "$work/efi-grub.cfg"
        mcopy -o -i "$work/efiboot.img" "$work/efi-grub.cfg" ::/EFI/BOOT/grub.cfg
        args+=(-update "$work/efiboot.img" /images/efiboot.img)
    fi
fi
if [ "${#args[@]}" -gt 0 ]; then
    xorriso -indev "$work/stage1.iso" -outdev "$out" -boot_image any replay "${args[@]}" >/dev/null
else
    cp "$work/stage1.iso" "$out"
fi
echo "Fertig: $out"
