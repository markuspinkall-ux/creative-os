#!/bin/bash
# Macht aus der Fedora-Netzinstallation die Creative-OS-Installation:
#  - Installer-Name „Creative OS“ (über ein updates.img mit eigener .buildstamp)
#  - Startmenü der ISO auf Deutsch und im Graphit-Look (GRUB-Thema, grub-theme/)
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
# Look: Graphit-Farben, Creative-Logo statt Fedora-Blau (Anaconda lädt
# /run/install/updates/anaconda-gtk.css mit Vorrang; die Bilder ersetzen die von Fedora)
here="$(cd "$(dirname "$0")" && pwd)"
if [ -d "$here/installer" ]; then
    cp "$here/installer/anaconda-gtk.css" "$work/upd/anaconda-gtk.css"
    mkdir -p "$work/upd/usr/share/anaconda/pixmaps" "$work/upd/etc/gtk-3.0" "$work/upd/etc/anaconda/conf.d"
    # Sicherer Weg: Anaconda lädt das eigene Stylesheet über seine Konfiguration
    # (custom_stylesheet, Vorrang vor den Fedora-Farben); updates.img legt sich über das System.
    cp "$here/installer/anaconda-gtk.css" "$work/upd/usr/share/anaconda/creative-gtk.css"
    printf '[User Interface]\ncustom_stylesheet = /usr/share/anaconda/creative-gtk.css\n' \
        > "$work/upd/etc/anaconda/conf.d/99-creative-os.conf"
    cp "$here"/installer/pixmaps/*.png "$work/upd/usr/share/anaconda/pixmaps/"
    # Bilder während der Installation: Creative OS statt Fedora-Hinweise
    mkdir -p "$work/upd/usr/share/anaconda/pixmaps/rnotes/en" "$work/upd/usr/share/anaconda/pixmaps/rnotes/de"
    cp "$here"/installer/rnotes/*.svg "$work/upd/usr/share/anaconda/pixmaps/rnotes/en/"
    cp "$here"/installer/rnotes/*.svg "$work/upd/usr/share/anaconda/pixmaps/rnotes/de/"
    # dunkle Grundfarben für alles, was die eigene Datei nicht abdeckt
    printf '[Settings]\ngtk-application-prefer-dark-theme=1\ngtk-font-name=Liberation Sans 11\n' > "$work/upd/etc/gtk-3.0/settings.ini"
fi
(cd "$work/upd" && find . | cpio -o -H newc --quiet | gzip -9) > "$work/updates.img"

# 2) Kickstart + updates.img einbauen
mkksiso --ks "$ks" --updates "$work/updates.img" "$src" "$work/stage1.iso"

# 3) Menüeinträge umbenennen (BIOS-, UEFI-Menü und das UEFI-Startabbild)
brand() {
    sed -i -E '/menuentry|submenu|menu label|^\s*label/ {
        s/Fedora( Linux)?( [0-9]+)?/Creative OS/g
        s/Install Creative OS in basic graphics mode/Creative OS im einfachen Grafikmodus installieren/
        s/Test this media & install Creative OS/Medium testen und Creative OS installieren/
        s/Install Creative OS/Creative OS installieren/
        s/Rescue a Creative OS system/Creative OS reparieren (Rettungsmodus)/
        s/Troubleshooting -->/Fehlerbehebung -->/
        s/Boot first drive/Von der ersten Festplatte starten/
        s/Return to main menu/Zurueck zum Hauptmenue/
    }' "$1"
    # ohne Datenträgerprüfung starten (die dauert mehrere Minuten)
    sed -i -E 's/^set default="1"/set default="0"/' "$1"
    # Graphit-Startmenü: nur wenn GRUB Schrift und Thema findet, sonst bleibt das Textmenü
    case "$1" in *grub*.cfg)
        [ -n "$theme_dir" ] || return 0
        snippet="$(cat "$here/grub-theme/grub-snippet.cfg")"
        [ "${CREATIVE_GRUB_DEBUG:-}" = 1 ] && snippet="set creative_debug=1
$snippet"
        awk -v block="$snippet" '
            !done && /^(menuentry|submenu) / { print block; print ""; done=1 } { print }' "$1" > "$1.neu" && mv "$1.neu" "$1" ;;
    esac
}

# GRUB-Thema (Graphit) samt Schriften für das Startmenü der ISO
theme_dir=""
if [ -d "$here/grub-theme" ] && command -v grub2-mkfont >/dev/null 2>&1; then
    theme_dir="$work/grub-theme"
    mkdir -p "$theme_dir"
    cp "$here"/grub-theme/*.png "$here"/grub-theme/theme.txt "$theme_dir/"
    sans=$(fc-match -f '%{file}' 'Liberation Sans:style=Regular' 2>/dev/null)
    bold=$(fc-match -f '%{file}' 'Liberation Sans:style=Bold' 2>/dev/null)
    if [ -f "$sans" ] && [ -f "$bold" ]; then
        # nur die nötigen Zeichen – sonst meldet GRUB „glyphs too large to fit on screen“
        # und bleibt im Textmodus (Latein + Umlaute, Gedankenstrich, Mittelpunkt, Pfeile)
        ranges="0x20-0x7E,0xA0-0x17F,0x2013-0x2014,0x2022-0x2022,0x2190-0x2193"
        for n in 18 20; do grub2-mkfont -r "$ranges" -s "$n" -o "$theme_dir/sans-$n.pf2" "$sans"; done
        for n in 20 36; do grub2-mkfont -r "$ranges" -s "$n" -o "$theme_dir/bold-$n.pf2" "$bold"; done
    else
        echo "Liberation-Schrift fehlt – Startmenü bleibt im Textmodus"; theme_dir=""
    fi
fi

args=()
[ -z "$theme_dir" ] || args+=(-map "$theme_dir" /boot/grub2/themes/creative)
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
