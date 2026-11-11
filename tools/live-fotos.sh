#!/bin/bash
# Testet die große Live-ISO in einer virtuellen Maschine (läuft auf GitHub):
#   Start → Live-Desktop mit Creative-Installation → automatischer Durchlauf (Datenträger CRTEST)
#   → echte Installation auf eine leere virtuelle Platte → Neustart von der Platte.
# Aufruf: live-fotos.sh <iso>     Ergebnis: live-fotos/*.png (+ uebersicht.png)
set -u
ISO="$1"
W="$PWD/live-fotos"; mkdir -p "$W"
command -v socat >/dev/null || sudo apt-get install -y -qq socat >/dev/null
OVMF_CODE=$(ls /usr/share/OVMF/OVMF_CODE_4M.fd /usr/share/OVMF/OVMF_CODE.fd 2>/dev/null | head -1)
OVMF_VARS=$(ls /usr/share/OVMF/OVMF_VARS_4M.fd /usr/share/OVMF/OVMF_VARS.fd 2>/dev/null | head -1)
n=0; same=0; last_sum=""
qmp() { printf '{"execute":"qmp_capabilities"}\n%s\n' "$1" | timeout 5 socat - UNIX-CONNECT:"$W/qmp.sock" >/dev/null 2>&1; }
shot() {
    qmp "{\"execute\":\"screendump\",\"arguments\":{\"filename\":\"$W/tmp.ppm\"}}"; sleep 1
    [ -f "$W/tmp.ppm" ] || return 1
    sum=$(md5sum < "$W/tmp.ppm" | cut -c1-12)
    if [ "$sum" = "$last_sum" ]; then same=$((same + 1)); rm -f "$W/tmp.ppm"; return 0; fi
    same=0; last_sum=$sum; n=$((n + 1))
    name=$(printf '%03d-%s' "$n" "$1")
    pnmtopng "$W/tmp.ppm" > "$W/$name.png" 2>/dev/null; rm -f "$W/tmp.ppm"
    echo "Bildschirmfoto: $name.png  ($(( $(date +%s) - start ))s)"
}
vm() {  # $@ = zusätzliche QEMU-Argumente
    rm -f "$W/qmp.sock"
    qemu-system-x86_64 -enable-kvm -machine q35 -cpu host -m 10240 -smp 4 \
        -drive if=pflash,format=raw,readonly=on,file="$OVMF_CODE" -drive if=pflash,format=raw,file="$W/vars.fd" \
        -drive file="$W/disk.qcow2",if=virtio,format=qcow2 \
        -nic user,model=virtio-net-pci \
        -vga none -device virtio-vga,xres=1280,yres=800 -usb -device usb-tablet \
        -serial file:"$W/serial-$2.log" \
        -display none -qmp unix:"$W/qmp.sock",server,nowait -daemonize -pidfile "$W/qemu.pid" $1 || return 1
    start=$(date +%s); last_sum=""; same=0
}
stop() { kill "$(cat "$W/qemu.pid")" 2>/dev/null; sleep 5; }

qemu-img create -q -f qcow2 "$W/disk.qcow2" 64G
cp "$OVMF_VARS" "$W/vars.fd"
# kleiner Datenträger „CRTEST“: startet in der Live-Umgebung den automatischen Durchlauf
truncate -s 64M "$W/crtest.img"; mkfs.vfat -n CRTEST "$W/crtest.img" >/dev/null

echo "=== 1) Live-ISO starten, Installation automatisch durchlaufen"
vm "-cdrom $ISO -boot d -drive file=$W/crtest.img,if=virtio,format=raw" live || { echo "QEMU startet nicht"; exit 1; }
for i in $(seq 1 60); do sleep 5; shot live; done          # Start, Desktop, Schritte der Installation
while :; do
    sleep 20; shot installation
    el=$(( $(date +%s) - start ))
    if [ "$el" -gt 900 ] && [ "$same" -ge 15 ]; then echo "Bild seit 5 Minuten unverändert – fertig"; break; fi
    if [ "$el" -gt 5400 ]; then echo "Zeitlimit erreicht"; break; fi
done
stop

echo "=== 2) Vom installierten System starten"
vm "" installiert || exit 1
for i in $(seq 1 40); do sleep 6; shot installiert; done
stop

python3 - "$W" <<'PY'
import sys, glob, os
from PIL import Image, ImageDraw
d = sys.argv[1]
files = sorted(glob.glob(os.path.join(d, "[0-9][0-9][0-9]-*.png")))
if not files: sys.exit(0)
if len(files) > 48:  # gleichmäßig auswählen
    step = len(files) / 48
    files = [files[int(i * step)] for i in range(48)] + [files[-1]]
tw, th, cols = 400, 250, 4
rows = (len(files) + cols - 1) // cols
sheet = Image.new("RGB", (cols * (tw + 12) + 12, rows * (th + 34) + 12), "#12151b")
dr = ImageDraw.Draw(sheet)
for i, f in enumerate(files):
    im = Image.open(f).convert("RGB"); im.thumbnail((tw, th))
    x = 12 + (i % cols) * (tw + 12); y = 12 + (i // cols) * (th + 34)
    sheet.paste(im, (x, y)); dr.text((x, y + th + 6), os.path.basename(f), fill="#dce6ff")
sheet.save(os.path.join(d, "uebersicht.png"))
print("Übersicht:", len(files), "Bilder")
PY
tail -5 "$W"/serial-*.log 2>/dev/null
ls "$W"/*.png | wc -l
