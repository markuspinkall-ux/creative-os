#!/bin/sh
# Lautsprecher-Korrektur (creative-ton-fix) in Fedora 44 prüfen:
# nachgebautes /sys für Galaxy Book2 Pro 955XED und andere Geräte, echte modprobe-Prüfung,
# und ob der Fedora-Kernel den Parameter hda_model im SOF-Modul wirklich hat.
set -eu
cd "$(dirname "$0")/.."
dnf install -y -q --setopt=install_weak_deps=False python3 kmod kernel-modules-core kernel-modules xz zstd >/dev/null

fake() {   # fake <ordner> <hersteller> <produkt> <subsystem-device>
    r="$1"; mkdir -p "$r/sys/class/dmi/id" "$r/sys/bus/pci/devices/0000:00:1f.3" "$r/etc"
    echo "$2" > "$r/sys/class/dmi/id/sys_vendor"; echo "$3" > "$r/sys/class/dmi/id/product_name"
    d="$r/sys/bus/pci/devices/0000:00:1f.3"
    echo 0x040100 > "$d/class"; echo 0x144d > "$d/subsystem_vendor"; echo "0x$4" > "$d/subsystem_device"
}
run() { CREATIVE_SYSFS="$1/sys" CREATIVE_ETC="$1/etc" python3 image/geraete/creative-ton-fix "$2"; }

W=$(mktemp -d)
# 1. Galaxy Book2 Pro 955XED: Korrektur mit 2 Verstärkern
fake "$W/book" "SAMSUNG ELECTRONICS CO., LTD." "955XED" c1c5
run "$W/book" --boot
grep -q "hda_model=alc298-samsung-amp-v2-2-amps" "$W/book/etc/modprobe.d/creative-ton-fix.conf"
run "$W/book" --boot | grep -q unverändert
run "$W/book" status
# von Hand: 4 Verstärker, dann aus, dann wieder automatisch
run "$W/book" 4 >/dev/null; grep -q "v2-4-amps" "$W/book/etc/modprobe.d/creative-ton-fix.conf"
run "$W/book" aus >/dev/null; [ ! -e "$W/book/etc/modprobe.d/creative-ton-fix.conf" ]
run "$W/book" auto >/dev/null; grep -q "v2-2-amps" "$W/book/etc/modprobe.d/creative-ton-fix.conf"
# nur Produktname passt (anderes Subsystem): trotzdem erkannt
fake "$W/book2" "SAMSUNG ELECTRONICS CO., LTD." "955XED" c999
run "$W/book2" --boot; grep -q "v2-2-amps" "$W/book2/etc/modprobe.d/creative-ton-fix.conf"
# 2. Andere Geräte: nichts schreiben
fake "$W/pc" "Micro-Star International Co., Ltd." "MS-7C91" c1c5
run "$W/pc" --boot; [ ! -e "$W/pc/etc/modprobe.d/creative-ton-fix.conf" ] || { echo "FEHLER: fremder PC bekam Korrektur"; exit 1; }
fake "$W/samsung-anders" "SAMSUNG ELECTRONICS CO., LTD." "750XFG" c1d0
run "$W/samsung-anders" --boot; [ ! -e "$W/samsung-anders/etc/modprobe.d/creative-ton-fix.conf" ]
echo "Erkennung: ok (955XED per Subsystem und Name, andere Geräte unberührt, 2/4/aus/auto)"

# 3. echte modprobe-Prüfung + Parameter im Fedora-Kernel
cp "$W/book/etc/modprobe.d/creative-ton-fix.conf" /etc/modprobe.d/
modprobe --showconfig | grep -E "options snd.sof.intel.hda.(common|generic) hda_model=" \
    || { echo "FEHLER: modprobe kennt die Option nicht"; exit 1; }
kv=$(ls /lib/modules | head -1)
echo "Kernel: $kv"
found=""
for m in snd-sof-intel-hda-common snd-sof-intel-hda-generic; do
    if modinfo -k "$kv" -p "$m" 2>/dev/null | grep -q "^hda_model:"; then echo "hda_model in $m: ja"; found=1; fi
done
[ -n "$found" ] || { echo "FEHLER: Parameter hda_model in keinem SOF-Modul"; exit 1; }
# Den Modellnamen muss der Realtek-Treiber dieses Kernels kennen
ko=$(modinfo -k "$kv" -n snd-hda-codec-alc269 2>/dev/null || modinfo -k "$kv" -n snd-hda-codec-realtek)
echo "Realtek-Treiber: $ko"
case "$ko" in *.xz) xz -dc "$ko" ;; *.zst) zstd -dc "$ko" ;; *.gz) gzip -dc "$ko" ;; *) cat "$ko" ;; esac > /tmp/realtek.ko
for m in alc298-samsung-amp-v2-2-amps alc298-samsung-amp-v2-4-amps; do
    grep -aq "$m" /tmp/realtek.ko || { echo "FEHLER: Modell $m fehlt im Kernel"; exit 1; }
    echo "Modell bekannt: $m"
done
grep -aq "Galaxy Book2 Pro (NP950XED)" /tmp/realtek.ko && echo "NP950XED (gleiche Verstärker) im Kernel: ja"
echo "Lautsprecher-Korrektur: ok"
