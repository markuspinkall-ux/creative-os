#!/bin/sh
# Start mit Secure Boot nachstellen (Fedora 44, QEMU + OVMF mit Microsoft-Schlüsseln):
# shim → signierter GRUB → GRUB-Konfiguration wie auf dem installierten System (bootupd, statisch)
# → user.cfg mit allem, was Gibeon OS hineinschreibt. Meldet GRUB „prohibited by secure boot
# policy“, schlägt die Prüfung fehl.
#   sh tools/secureboot-test.sh <ausgabeordner>
set -eu
cd "$(dirname "$0")/.."
OUT="$(realpath -m "${1:-secureboot-fotos}")"
mkdir -p "$OUT"
dnf install -y -q --setopt=install_weak_deps=False shim-x64 grub2-efi-x64 grub2-tools grub2-tools-extra bootupd \
    edk2-ovmf qemu-system-x86-core dosfstools mtools liberation-sans-fonts fontconfig python3-pillow socat \
    kernel-core >/dev/null
W="$(mktemp -d)"

echo "--- bootupd: statische GRUB-Dateien ---"
find /usr/lib/bootupd -type f | sort
for f in $(find /usr/lib/bootupd -name '*.cfg' | sort); do echo "===== $f"; cat "$f"; done

# ---- GRUB-Thema wie creative-grub-design es anlegt -----------------------------------------
SRC="$W/share"; mkdir -p "$SRC"
cp image/netinstall/grub-theme/background.png image/netinstall/grub-theme/logo.png image/netinstall/grub-theme/select_*.png "$SRC/"
cp image/grub-theme/theme.txt image/grub-theme/grub-snippet.cfg "$SRC/"
sans=$(fc-match -f '%{file}' 'Liberation Sans:style=Regular'); bold=$(fc-match -f '%{file}' 'Liberation Sans:style=Bold')
ranges="0x20-0x7E,0xA0-0x17F,0x2013-0x2014,0x2022-0x2022,0x2190-0x2193"
for n in 18 20; do grub2-mkfont -r "$ranges" -s "$n" -o "$SRC/sans-$n.pf2" "$sans"; done
for n in 20 36; do grub2-mkfont -r "$ranges" -s "$n" -o "$SRC/bold-$n.pf2" "$bold"; done
(cd "$SRC" && cat theme.txt grub-snippet.cfg *.png *.pf2 | sha256sum | cut -c1-16 > version)

# ---- /boot wie auf dem installierten System --------------------------------------------------
BOOT="$W/boot"; mkdir -p "$BOOT/grub2" "$BOOT/loader/entries"
static=$(find /usr/lib/bootupd -name 'grub-static-pre.cfg' | head -n 1)
if [ -n "$static" ]; then
    d=$(dirname "$static")
    { cat "$static"; [ -d "$d/configs.d" ] && cat "$d"/configs.d/*.cfg 2>/dev/null; cat "$d/grub-static-post.cfg" 2>/dev/null || true; } > "$BOOT/grub2/grub.cfg"
else
    echo "Hinweis: keine statische bootupd-Konfiguration gefunden – nehme eine einfache"
    printf 'if [ -f ${config_directory}/user.cfg ]; then source ${config_directory}/user.cfg; fi\nblscfg\n' > "$BOOT/grub2/grub.cfg"
fi
grep -q user.cfg "$BOOT/grub2/grub.cfg" || echo 'if [ -f ${config_directory}/user.cfg ]; then source ${config_directory}/user.cfg; fi' >> "$BOOT/grub2/grub.cfg"
kver=$(ls /usr/lib/modules | head -n 1)
cp "/usr/lib/modules/$kver/vmlinuz" "$BOOT/vmlinuz-test"
cat > "$BOOT/loader/entries/ostree-1.conf" <<CONF
title Gibeon OS 3 (Test)
version 1
linux /vmlinuz-test
options console=ttyS0 panic=-1
CONF
# user.cfg: genau wie creative-quiet-boot, creative-grub-menue und creative-grub-design
printf '# creative-os: GRUB-Textmeldungen unsichtbar\nset color_normal=black/black\nset menu_color_normal=light-gray/black\nset menu_color_highlight=white/dark-gray\n' > "$BOOT/grub2/user.cfg"
export CREATIVE_GRUB_SRC="$SRC" CREATIVE_BOOT_DIRS="$BOOT/grub2" CREATIVE_GRUB_AUS="$W/aus" CREATIVE_GRUB_ZEIGEN="$W/zeigen"
sh image/grub-theme/creative-grub-menue
sh image/grub-theme/creative-grub-design
echo "--- grub.cfg ---"; cat "$BOOT/grub2/grub.cfg"; echo "--- user.cfg ---"; cat "$BOOT/grub2/user.cfg"

# ---- Festplatte: EFI-Partition (shim, GRUB) + /boot (FAT, reicht GRUB) ------------------------
EFI="$W/efi"; mkdir -p "$EFI/EFI/BOOT" "$EFI/EFI/fedora"
cp /boot/efi/EFI/fedora/shimx64.efi "$EFI/EFI/BOOT/BOOTX64.EFI"
cp /boot/efi/EFI/fedora/shimx64.efi /boot/efi/EFI/fedora/grubx64.efi "$EFI/EFI/fedora/"
cp /boot/efi/EFI/fedora/grubx64.efi "$EFI/EFI/BOOT/"
cp /boot/efi/EFI/fedora/mmx64.efi "$EFI/EFI/BOOT/" 2>/dev/null || true
efistub=$(find /usr/lib/bootupd -name 'grub-static-efi.cfg' | head -n 1)
if [ -n "$efistub" ]; then cp "$efistub" "$EFI/EFI/fedora/grub.cfg"
else printf 'search --label boot --set prefix --no-floppy\nset prefix=($prefix)/grub2\nconfigfile $prefix/grub.cfg\n' > "$EFI/EFI/fedora/grub.cfg"; fi
cp "$EFI/EFI/fedora/grub.cfg" "$EFI/EFI/BOOT/grub.cfg"
echo "--- EFI-grub.cfg ---"; cat "$EFI/EFI/fedora/grub.cfg"
mk() {   # $1 Bild, $2 Ordner, $3 Name
    truncate -s 200M "$1"; mkfs.vfat -n "$3" "$1" >/dev/null
    (cd "$2" && find . -type d | sed 's#^\./##' | grep -v '^\.$' | while read -r d; do mmd -i "$1" "::/$d"; done
     find . -type f | sed 's#^\./##' | while read -r f; do mcopy -i "$1" "$f" "::/$f"; done)
}
mk "$W/efi.img" "$EFI" EFI
mk "$W/boot.img" "$BOOT" boot

# ---- Start mit Secure Boot ---------------------------------------------------------------------
CODE=/usr/share/edk2/ovmf/OVMF_CODE.secboot.fd
VARS=/usr/share/edk2/ovmf/OVMF_VARS.secboot.fd
ls /usr/share/edk2/ovmf/
cp "$VARS" "$W/vars.fd"
foto() {
    echo '{"execute":"qmp_capabilities"}{"execute":"screendump","arguments":{"filename":"'"$W/s.ppm"'"}}' \
        | socat - UNIX-CONNECT:"$W/qmp.sock" >/dev/null 2>&1 || return 0
    sleep 1
    python3 -c "from PIL import Image; Image.open('$W/s.ppm').save('$1')" 2>/dev/null || true
}
qemu-system-x86_64 -machine q35,smm=on -global driver=cfi.pflash01,property=secure,value=on -m 1024 \
    -drive if=pflash,format=raw,unit=0,readonly=on,file="$CODE" \
    -drive if=pflash,format=raw,unit=1,file="$W/vars.fd" \
    -drive file="$W/efi.img",format=raw,if=virtio -drive file="$W/boot.img",format=raw,if=virtio \
    -vga std -display none -serial file:"$OUT/serial.log" \
    -qmp unix:"$W/qmp.sock",server,nowait -daemonize -pidfile "$W/qemu.pid"
for i in $(seq 1 12); do sleep 10; foto "$OUT/start-$(printf %03d $((i*10))).png"; done
kill "$(cat "$W/qemu.pid")" 2>/dev/null || true
echo "--- serielle Ausgabe ---"; cat "$OUT/serial.log" | tr -d '\r' | sed 's/\x1b\[[0-9;?]*[A-Za-z]//g' | tail -c 6000; echo
if grep -a "prohibited by secure boot" "$OUT/serial.log"; then
    echo "FEHLER: GRUB meldet „prohibited by secure boot policy“"; exit 1
fi
grep -aq "Linux version" "$OUT/serial.log" && echo "Kernel startet unter Secure Boot" || echo "Hinweis: Kernel-Start nicht in der seriellen Ausgabe"
