#!/bin/bash
# Fotografiert die Creative-OS-Installation (läuft auf GitHub):
#   build  – kleine Installations-ISOs bauen (zum Umschauen und vollautomatisch)
#   run    – beide in QEMU starten und regelmäßig Bildschirmfotos machen
# Ergebnis: installer-fotos/*.png (+ uebersicht.png)
set -u
W="$PWD/installer-fotos"; mkdir -p "$W"
VARIANT=amd

if [ "${1:-}" = build ]; then
    owner="$(echo "${OWNER:-markuspinkall-ux}" | tr '[:upper:]' '[:lower:]')"
    mkdir -p "$W/iso"
    sed "s|@IMAGE@|ghcr.io/${owner}/creative-os:${VARIANT}|" image/netinstall/creative.ks.in > "$W/iso/umschauen.ks"
    # vollautomatisch: Festplatte leeren, Benutzer anlegen – damit man den Fortschritt sieht
    awk '/^%post/ && !done { print "zerombr\nclearpart --all --initlabel\nautopart --type=btrfs --noswap\nrootpw --lock\nuser --name=creative --password=creative --plaintext --groups=wheel\n"; done=1 } { print }' \
        "$W/iso/umschauen.ks" > "$W/iso/automatisch.ks"
    sudo podman run --rm --privileged -v "$W/iso:/out" -v "$PWD:/src:ro" registry.fedoraproject.org/fedora:44 bash -euc '
        dnf install -y -q --setopt=install_weak_deps=False lorax xorriso curl cpio gzip mtools grub2-tools-extra liberation-sans-fonts fontconfig >/dev/null
        base=https://download.fedoraproject.org/pub/fedora/linux/releases/44/Everything/x86_64/iso
        iso=$(curl -fsSL "$base/" | grep -o "Fedora-Everything-netinst-x86_64-[0-9.-]*\.iso" | head -n1)
        for try in 1 2 3 4; do curl -fsSL --retry 3 -o /tmp/netinst.iso "$base/$iso" && [ "$(dd if=/tmp/netinst.iso bs=1 skip=32769 count=5 2>/dev/null)" = CD001 ] && break; echo "Download unvollständig – neuer Versuch"; sleep 20; done; [ "$(dd if=/tmp/netinst.iso bs=1 skip=32769 count=5 2>/dev/null)" = CD001 ]
        for k in umschauen automatisch; do
            CREATIVE_GRUB_DEBUG=1 bash /src/image/netinstall/brand-iso.sh /tmp/netinst.iso "/out/$k.ks" "/out/$k.iso"
        done
        # zur Kontrolle: das umgebaute Startmenü
        xorriso -osirrox on -indev /out/umschauen.iso -extract /EFI/BOOT/grub.cfg /out/grub.cfg >/dev/null 2>&1 || true
        xorriso -indev /out/umschauen.iso -find /boot/grub2/themes 2>/dev/null | head -20 || true
    ' || exit 1
    sudo chown -R "$USER" "$W/iso"
    echo "--- Startmenü (EFI):"; head -40 "$W/iso/grub.cfg" 2>/dev/null
    ls -lh "$W/iso"/*.iso
    exit 0
fi

# ---- run ---------------------------------------------------------------------------------
command -v socat >/dev/null || sudo apt-get install -y -qq socat >/dev/null
OVMF_CODE=$(ls /usr/share/OVMF/OVMF_CODE_4M.fd /usr/share/OVMF/OVMF_CODE.fd 2>/dev/null | head -1)
OVMF_VARS=$(ls /usr/share/OVMF/OVMF_VARS_4M.fd /usr/share/OVMF/OVMF_VARS.fd 2>/dev/null | head -1)
n=0
qmp() { printf '{"execute":"qmp_capabilities"}\n%s\n' "$1" | timeout 5 socat - UNIX-CONNECT:"$W/qmp.sock" >/dev/null 2>&1; }
key() { for k in "$@"; do qmp "{\"execute\":\"send-key\",\"arguments\":{\"keys\":[{\"type\":\"qcode\",\"data\":\"$k\"}]}}"; sleep 0.4; done; }
click() {  # absolute Mausposition (usb-tablet, 0…32767) und Linksklick
    x=$(( $1 * 32767 / 1280 )); y=$(( $2 * 32767 / 800 ))
    qmp "{\"execute\":\"input-send-event\",\"arguments\":{\"events\":[{\"type\":\"abs\",\"data\":{\"axis\":\"x\",\"value\":$x}},{\"type\":\"abs\",\"data\":{\"axis\":\"y\",\"value\":$y}}]}}"
    sleep 0.3
    qmp '{"execute":"input-send-event","arguments":{"events":[{"type":"btn","data":{"down":true,"button":"left"}}]}}'; sleep 0.15
    qmp '{"execute":"input-send-event","arguments":{"events":[{"type":"btn","data":{"down":false,"button":"left"}}]}}'
}
# Bildschirmfoto; doppelte (unveränderte) Bilder werden verworfen
shot() {
    qmp "{\"execute\":\"screendump\",\"arguments\":{\"filename\":\"$W/tmp.ppm\"}}"; sleep 1
    [ -f "$W/tmp.ppm" ] || return 1
    sum=$(md5sum < "$W/tmp.ppm" | cut -c1-12)
    if [ "$sum" = "${last_sum:-}" ]; then same=$((same + 1)); rm -f "$W/tmp.ppm"; return 0; fi
    same=0; last_sum=$sum; n=$((n + 1))
    name=$(printf '%02d-%s' "$n" "$1")
    pnmtopng "$W/tmp.ppm" > "$W/$name.png" 2>/dev/null; rm -f "$W/tmp.ppm"
    echo "Bildschirmfoto: $name.png  ($(( $(date +%s) - start ))s)"
}
boot() {  # $1 = ISO
    rm -f "$W/disk.qcow2" "$W/qmp.sock"; qemu-img create -q -f qcow2 "$W/disk.qcow2" 40G
    cp "$OVMF_VARS" "$W/vars.fd"
    qemu-system-x86_64 -enable-kvm -machine q35 -cpu host -m 8192 -smp 4 \
        -drive if=pflash,format=raw,readonly=on,file="$OVMF_CODE" -drive if=pflash,format=raw,file="$W/vars.fd" \
        -drive file="$W/disk.qcow2",if=virtio,format=qcow2 \
        -cdrom "$1" -boot d \
        -nic user,model=virtio-net-pci \
        -vga none -device virtio-vga,xres=1280,yres=800 -usb -device usb-tablet \
        -display none -qmp unix:"$W/qmp.sock",server,nowait -daemonize -pidfile "$W/qemu.pid" || return 1
    start=$(date +%s); last_sum=""; same=0
}
stop() { kill "$(cat "$W/qemu.pid")" 2>/dev/null; sleep 3; }

echo "=== 1) Startmenü und Übersicht des Installers"
boot "$W/iso/umschauen.iso" || { echo "QEMU startet nicht"; exit 1; }
# Startmenü abwarten (UEFI braucht ein paar Sekunden), dabei immer wieder fotografieren
for i in $(seq 1 40); do sleep 1; shot startmenue; done
key down; sleep 1; shot startmenue-auswahl; key up; sleep 1
key ret
for i in $(seq 1 30); do sleep 10; shot installer; done
# Übersicht → „Benutzer anlegen“ antippen (Position aus der Übersicht bei 1280×800)
click 979 397; sleep 6; shot benutzer
stop

echo "=== 2) Vollautomatische Installation (Fortschritt)"
boot "$W/iso/automatisch.iso" || { echo "QEMU startet nicht"; exit 1; }
sleep 12; key ret
while :; do
    sleep 30; shot installation
    el=$(( $(date +%s) - start ))
    if [ "$el" -gt 600 ] && [ "$same" -ge 10 ]; then echo "Bild seit 5 Minuten unverändert – fertig"; break; fi
    if [ "$el" -gt 4200 ]; then echo "Zeitlimit erreicht"; break; fi
done
stop

# Übersicht (Kontaktbogen)
python3 - "$W" <<'PY'
import sys, glob, os
from PIL import Image, ImageDraw
d = sys.argv[1]
files = sorted(glob.glob(os.path.join(d, "[0-9][0-9]-*.png")))
if not files: sys.exit(0)
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
ls "$W"/*.png | wc -l
