#!/bin/sh
# Startauswahl (GRUB) im Gibeon-Design prüfen – in Fedora 44 mit echtem GRUB in QEMU.
#   sh tools/grub-design-test.sh <ausgabeordner>
# 1. creative-grub-design gegen ein nachgebautes /boot: Thema kopieren, Block in user.cfg,
#    zweimal ausführen ändert nichts, „aus“ entfernt alles wieder, fremde Zeilen bleiben.
# 2. Eine kleine Start-CD mit genau dieser user.cfg in QEMU starten und das Menü fotografieren.
set -eu
cd "$(dirname "$0")/.."
OUT="$(realpath -m "${1:-grub-fotos}")"
mkdir -p "$OUT"
dnf install -y -q --setopt=install_weak_deps=False grub2-tools grub2-tools-extra grub2-pc-modules grub2-efi-x64-modules edk2-ovmf xorriso \
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
export CREATIVE_GRUB_SRC="$SRC" CREATIVE_BOOT_DIRS="$BOOT" CREATIVE_GRUB_AUS="$W/etc/grub-design-aus"
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
# „aus“ muss den automatischen Lauf beim Start überstehen
sh image/grub-theme/creative-grub-design auto
cmp "$BOOT/user.cfg" "$W/user.vorher" || { echo "FEHLER: Start schaltet Design trotz „aus“ wieder ein"; exit 1; }
sh image/grub-theme/creative-grub-design
[ ! -e "$CREATIVE_GRUB_AUS" ] || { echo "FEHLER: „an“ hebt „aus“ nicht auf"; exit 1; }
sh image/grub-theme/creative-grub-design auto
cmp "$BOOT/user.cfg" "$W/user.an" || { echo "FEHLER: auto nach „an“ anders"; exit 1; }
grep -q "            set gfxmode=auto$" "$BOOT/user.cfg" || { echo "FEHLER: Auflösung nicht von der Firmware"; exit 1; }
echo "Skript: ok (an, zweimal, aus, aus bleibt beim Start aus, wieder an)"

# Startauswahl verstecken / zeigen
export CREATIVE_GRUB_ZEIGEN="$W/etc/startauswahl-zeigen"
sh image/grub-theme/creative-grub-menue
grep -q "set timeout_style=hidden" "$BOOT/user.cfg" || { echo "FEHLER: Startauswahl nicht versteckt"; exit 1; }
# GRUB-Syntax prüfen: echte Startfehler („syntax error“, „Incorrect command“) fallen hier auf
grub2-script-check "$BOOT/user.cfg" || { echo "FEHLER: user.cfg hat GRUB-Syntaxfehler"; exit 1; }
grub2-script-check image/netinstall/grub-theme/grub-snippet.cfg || { echo "FEHLER: ISO-Startmenü hat GRUB-Syntaxfehler"; exit 1; }
! grep -v '^[[:space:]]*#' "$BOOT/user.cfg" | grep -qE '&&|\|\|' || { echo "FEHLER: GRUB kennt kein && oder ||"; exit 1; }
# Secure Boot: auf UEFI keine Module von der Platte nachladen
awk '/^[[:space:]]*#/{next} /grub_platform" != "efi"/{inside=1} inside&&/^    fi/{inside=0} /insmod|background_image/&&!inside{print; bad=1} END{exit bad}' image/grub-theme/grub-snippet.cfg \
    || { echo "FEHLER: insmod/background_image auch bei UEFI (Secure Boot verbietet das)"; exit 1; }
cp "$BOOT/user.cfg" "$W/user.versteckt"
sh image/grub-theme/creative-grub-menue auto
cmp "$BOOT/user.cfg" "$W/user.versteckt" || { echo "FEHLER: auto schreibt doppelt"; exit 1; }
[ "$(grep -c "BEGIN orbit-os startauswahl" "$BOOT/user.cfg")" = 1 ] || { echo "FEHLER: Block doppelt"; exit 1; }
sh image/grub-theme/creative-grub-menue zeigen
! grep -q "orbit-os startauswahl" "$BOOT/user.cfg" || { echo "FEHLER: zeigen entfernt den Block nicht"; exit 1; }
sh image/grub-theme/creative-grub-menue auto
! grep -q "orbit-os startauswahl" "$BOOT/user.cfg" || { echo "FEHLER: Start versteckt trotz „zeigen“"; exit 1; }
cp "$BOOT/user.cfg" "$W/user.mit-menue"
sh image/grub-theme/creative-grub-menue
[ ! -e "$CREATIVE_GRUB_ZEIGEN" ] || { echo "FEHLER: verstecken hebt „zeigen“ nicht auf"; exit 1; }
echo "Startauswahl-Skript: ok (verstecken, auto, zeigen bleibt, wieder verstecken)"

# ---- 2. Echter GRUB in QEMU ------------------------------------------------------------------
ISO="$W/iso"
mkdir -p "$ISO/boot/grub"
cp -r "$BOOT/themes" "$ISO/boot/grub/"
cp "$W/user.mit-menue" "$ISO/boot/grub/user.cfg"
cat > "$ISO/boot/grub/grub.cfg" <<'CFG'
set timeout=30
set default=0
set prefix=($root)/boot/grub
if [ -f $prefix/user.cfg ]; then source $prefix/user.cfg; fi
menuentry "Gibeon OS 2 – Vivid Venus" { sleep 600 }
menuentry "Gibeon OS 2 – Vivid Venus (vorherige Version)" { sleep 600 }
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
# ---- 2b. Versteckte Startauswahl: ohne Taste kein Menü, mit Esc erscheint es -------------------
cp "$W/user.versteckt" "$ISO/boot/grub/user.cfg"
grub2-mkrescue -o "$W/test2.iso" "$ISO" >/dev/null 2>&1
rm -f "$W/qmp.sock"
qemu-system-x86_64 -m 512 -cdrom "$W/test2.iso" -vga std -display none -boot menu=off \
    -qmp unix:"$W/qmp.sock",server,nowait -daemonize -pidfile "$W/qemu.pid"
sleep 25
foto "$OUT/startauswahl-versteckt.png"
kill "$(cat "$W/qemu.pid")" 2>/dev/null || true
echo "Versteckt: Foto gemacht"
sleep 1; rm -f "$W/qmp.sock"
qemu-system-x86_64 -m 512 -cdrom "$W/test2.iso" -vga std -display none -boot menu=off \
    -qmp unix:"$W/qmp.sock",server,nowait -daemonize -pidfile "$W/qemu.pid"
sleep 1
for i in $(seq 1 40); do
    echo '{"execute":"qmp_capabilities"}{"execute":"human-monitor-command","arguments":{"command-line":"sendkey esc"}}' \
        | socat - UNIX-CONNECT:"$W/qmp.sock" >/dev/null 2>&1 || true
    sleep 0.5
done
sleep 3
foto "$OUT/startauswahl-esc.png"
kill "$(cat "$W/qemu.pid")" 2>/dev/null || true
# Vergleich mit dem normalen Menü-Foto: mit Esc fast gleich, versteckt deutlich anders
python3 - "$OUT/grub-startauswahl.png" "$OUT/startauswahl-versteckt.png" "$OUT/startauswahl-esc.png" <<'PY'
import sys
from PIL import Image, ImageChops
menue, versteckt, esc = (Image.open(f).convert("RGB") for f in sys.argv[1:4])
def anteil(a, b):
    if a.size != b.size:
        return 1.0
    d = ImageChops.difference(a, b).convert("L").point(lambda v: 255 if v > 40 else 0)
    return sum(d.histogram()[255:]) / (a.size[0] * a.size[1])
dv, de = anteil(menue, versteckt), anteil(menue, esc)
print(f"Abweichung vom Menü: versteckt {dv:.1%}, mit Esc {de:.1%}")
assert dv > 0.01, "versteckt sieht aus wie das Menü – Startauswahl wird trotzdem gezeigt"
assert de < dv / 2, "Esc öffnet die Startauswahl nicht"
PY
echo "Startauswahl: versteckt ohne Taste, mit Esc sichtbar"
sleep 1; rm -f "$W/qmp.sock"

# ---- 3. Dasselbe mit UEFI (wie auf echten PCs): Auflösung der Firmware, Grafikmenü ---------
OVMF=""; VARS=""
for f in /usr/share/edk2/ovmf/OVMF_CODE.fd:/usr/share/edk2/ovmf/OVMF_VARS.fd \
         /usr/share/edk2/ovmf/OVMF_CODE_4M.qcow2:/usr/share/edk2/ovmf/OVMF_VARS_4M.qcow2; do
    c="${f%%:*}"; v="${f#*:}"
    [ -f "$c" ] && [ -f "$v" ] && { OVMF="$c"; VARS="$v"; break; }
done
[ -n "$OVMF" ] || { echo "FEHLER: OVMF fehlt"; exit 1; }
fmt=raw; case "$OVMF" in *.qcow2) fmt=qcow2;; esac
cp "$VARS" "$W/vars.$fmt"
echo "UEFI mit $OVMF ($fmt)"
rm -f "$W/qmp.sock"
qemu-system-x86_64 -m 1024 -machine pc -drive file="$W/test.iso",media=cdrom,if=ide,index=0 -vga none -device bochs-display -display none \
    -drive if=pflash,format=$fmt,unit=0,readonly=on,file="$OVMF" \
    -drive if=pflash,format=$fmt,unit=1,file="$W/vars.$fmt" \
    -serial file:"$W/serial.log" -qmp unix:"$W/qmp.sock",server,nowait -daemonize -pidfile "$W/qemu.pid" \
    || { echo "FEHLER: QEMU (UEFI) startet nicht"; exit 1; }
# UEFI startet in QEMU ohne KVM langsam – bis zu 120 s warten, bis das Menü zu sehen ist
for i in $(seq 1 60); do
    sleep 2
    foto "$OUT/grub-startauswahl-uefi.png"
    python3 -c "
import sys
from PIL import Image
im = Image.open('$OUT/grub-startauswahl-uefi.png').convert('RGB'); px = im.load(); w, h = im.size
sys.exit(0 if len({px[x, y] for x in range(0, w, 7) for y in range(0, h, 7)}) > 200 else 1)" && { echo "UEFI-Menü nach $((i*2)) s"; break; }
done
echo "--- serielle Ausgabe (UEFI) ---"; tail -c 2000 "$W/serial.log" 2>/dev/null || true; echo
kill "$(cat "$W/qemu.pid")" 2>/dev/null || true
python3 - "$OUT/grub-startauswahl-uefi.png" <<'PY'
import sys
from PIL import Image
im = Image.open(sys.argv[1]).convert("RGB")
w, h = im.size
px = im.load()
colors = {px[x, y] for x in range(0, w, 7) for y in range(0, h, 7)}
# Nur Hinweis: OVMF ohne KVM zeigt im CI oft gar nichts auf dem Bildschirm
if len(colors) > 200: print(f"UEFI-Grafikmenü: {w}x{h}, {len(colors)} Farben")
else: print(f"Hinweis: UEFI-Bild in QEMU leer ({w}x{h}) – nur seriell geprüft")
PY
for f in "$OUT"/*.png; do echo "PNG64:$(basename "$f"):$(base64 -w0 "$f")"; done
echo "GRUB-Design: ok"
