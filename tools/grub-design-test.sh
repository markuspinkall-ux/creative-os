#!/bin/sh
# Startauswahl (GRUB) im Orbit-Design prüfen – in Fedora 44 mit echtem GRUB in QEMU.
#   sh tools/grub-design-test.sh <ausgabeordner>
# 1. creative-grub-design gegen ein nachgebautes /boot: Thema kopieren, Block in user.cfg,
#    zweimal ausführen ändert nichts, „aus“ entfernt alles wieder, fremde Zeilen bleiben.
# 2. Eine kleine Start-CD mit genau dieser user.cfg in QEMU starten und das Menü fotografieren.
set -eu
cd "$(dirname "$0")/.."
OUT="$(realpath -m "${1:-grub-fotos}")"
mkdir -p "$OUT"
dnf install -y -q --setopt=install_weak_deps=False grub2-tools grub2-tools-extra grub2-pc-modules xorriso \
    qemu-system-x86-core liberation-sans-fonts fontconfig python3-pillow mtools socat diffutils gawk >/dev/null

W="$(mktemp -d)"
SRC="$W/share"
mkdir -p "$SRC"
cp image/netinstall/grub-theme/background.png image/netinstall/grub-theme/logo.png image/netinstall/grub-theme/select_*.png "$SRC/"
cp image/grub-theme/theme.txt image/grub-theme/grub-snippet.cfg "$SRC/"
sans=$(fc-match -f '%{file}' 'Liberation Sans:style=Regular'); bold=$(fc-match -f '%{file}' 'Liberation Sans:style=Bold')
ranges="0x20-0x7E,0xA0-0x17F,0x2013-0x2014,0x2022-0x2022,0x2190-0x2193"
for n in 18 20; do grub2-mkfont -r "$ranges" -s "$n" -o "$SRC/sans-$n.pf2" "$sans"; done
for n in 20 36; do grub2-mkfont -r "$ranges" -s "$n" -o "$SRC/bold-$n.pf2" "$bold"; done
(cd "$SRC" && cat theme.txt grub-snippet.cfg *.png *.pf2 | sha256sum | cut -c1-16 > version)

# ---- 1. Skript gegen ein nachgebautes /boot ------------------------------------------------
BOOT="$W/boot/grub2"
mkdir -p "$BOOT"
printf 'set timeout=5\nif [ -f ${config_directory}/user.cfg ]; then source ${config_directory}/user.cfg; fi\n' > "$BOOT/grub.cfg"
# so sieht user.cfg nach creative-quiet-boot aus
printf '# creative-os: GRUB-Textmeldungen unsichtbar\nset color_normal=black/black\nset menu_color_normal=light-gray/black\nset menu_color_highlight=white/dark-gray\n' > "$BOOT/user.cfg"
cp "$BOOT/user.cfg" "$W/user.vorher"
export CREATIVE_GRUB_SRC="$SRC" CREATIVE_BOOT_DIRS="$BOOT"
sh image/grub-theme/creative-grub-design
grep -q "### BEGIN creative-os grub-design" "$BOOT/user.cfg"
grep -q "color_normal=black/black" "$BOOT/user.cfg" || { echo "FEHLER: fremde Zeilen verloren"; exit 1; }
[ -f "$BOOT/themes/creative/theme.txt" ] && [ -f "$BOOT/themes/creative/bold-36.pf2" ]
cp "$BOOT/user.cfg" "$W/user.an"
sh image/grub-theme/creative-grub-design
cmp "$BOOT/user.cfg" "$W/user.an" || { echo "FEHLER: zweiter Lauf ändert user.cfg"; exit 1; }
[ "$(grep -c 'BEGIN creative-os grub-design' "$BOOT/user.cfg")" = 1 ]
sh image/grub-theme/creative-grub-design aus
cmp "$BOOT/user.cfg" "$W/user.vorher" || { echo "FEHLER: „aus“ stellt user.cfg nicht wieder her"; exit 1; }
[ ! -d "$BOOT/themes/creative" ] || { echo "FEHLER: Thema nach „aus“ noch da"; exit 1; }
sh image/grub-theme/creative-grub-design
echo "Skript: ok (an, zweimal, aus, wieder an)"

# ---- 2. Echter GRUB in QEMU ------------------------------------------------------------------
ISO="$W/iso"
mkdir -p "$ISO/boot/grub"
cp -r "$BOOT/themes" "$BOOT/user.cfg" "$ISO/boot/grub/"
cat > "$ISO/boot/grub/grub.cfg" <<'CFG'
set timeout=30
set default=0
set prefix=($root)/boot/grub
if [ -f $prefix/user.cfg ]; then source $prefix/user.cfg; fi
menuentry "Orbit OS 2 – Vivid Venus" { sleep 600 }
menuentry "Orbit OS 2 – Vivid Venus (vorherige Version)" { sleep 600 }
menuentry "UEFI-Firmware-Einstellungen" { sleep 600 }
CFG
grub2-mkrescue -o "$W/test.iso" "$ISO" >/dev/null 2>&1
foto() {
    echo '{"execute":"qmp_capabilities"}{"execute":"screendump","arguments":{"filename":"'"$W/s.ppm"'"}}' \
        | socat - UNIX-CONNECT:"$W/qmp.sock" >/dev/null
    sleep 1
    python3 -c "from PIL import Image; Image.open('$W/s.ppm').save('$1')"
}
qemu-system-x86_64 -m 512 -cdrom "$W/test.iso" -vga std -display none -qmp unix:"$W/qmp.sock",server,nowait \
    -daemonize -pidfile "$W/qemu.pid"
sleep 25
foto "$OUT/grub-startauswahl.png"
echo '{"execute":"qmp_capabilities"}{"execute":"human-monitor-command","arguments":{"command-line":"sendkey down"}}' \
    | socat - UNIX-CONNECT:"$W/qmp.sock" >/dev/null
sleep 2
foto "$OUT/grub-startauswahl-vorherige.png"
kill "$(cat "$W/qemu.pid")" 2>/dev/null || true
python3 - "$OUT/grub-startauswahl.png" <<'PY'
import sys
from PIL import Image
im = Image.open(sys.argv[1]).convert("RGB")
w, h = im.size
px = im.load()
colors = {px[x, y] for x in range(0, w, 7) for y in range(0, h, 7)}
# Grafikmodus mit Hintergrundbild hat hunderte Farben, das Textmenü nur eine Handvoll
assert len(colors) > 200, f"kein Grafikmenü ({len(colors)} Farben, {w}x{h})"
print(f"Grafikmenü: {w}x{h}, {len(colors)} Farben")
PY
echo "GRUB-Design: ok"
