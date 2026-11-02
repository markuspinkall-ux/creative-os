# --- Creative OS: Nacharbeiten nach der Installation (Kickstart %post) ---
# 1) Secure Boot: Schlüssel der Creative-OS-Treiber zur Freischaltung vormerken.
#    Beim nächsten Start fragt ein blauer Bildschirm danach – Passwort: creative
if [ -d /sys/firmware/efi ] && mokutil --sb-state 2>/dev/null | grep -qi enabled; then
    printf 'creative\ncreative\n' | mokutil --import /usr/share/creative-os/secureboot/creative-os-mok.der || true
fi
# 2) Eintrag im Startmenü des PCs (UEFI): „Creative OS“ statt „Fedora“
if [ -d /sys/firmware/efi ] && command -v efibootmgr >/dev/null 2>&1; then
    num=$(efibootmgr 2>/dev/null | grep -E '^Boot[0-9A-F]{4}\*? +Fedora' | head -1 | sed -E 's/^Boot([0-9A-F]{4}).*/\1/')
    esp=$(findmnt -n -o SOURCE /boot/efi 2>/dev/null)
    [ -n "$esp" ] || esp=$(lsblk -lnpo NAME,PARTTYPE | awk 'tolower($2)=="c12a7328-f81f-11d2-ba4b-00a0c93ec93b"{print $1; exit}')
    if [ -n "$num" ] && [ -n "$esp" ]; then
        disk="/dev/$(lsblk -no PKNAME "$esp" | head -1)"
        part=$(cat "/sys/class/block/$(basename "$esp")/partition" 2>/dev/null)
        loader='\EFI\fedora\shimx64.efi'
        if [ -b "$disk" ] && [ -n "$part" ] && efibootmgr -q -c -d "$disk" -p "$part" -L "Creative OS" -l "$loader"; then
            efibootmgr -q -b "$num" -B || true
        fi
    fi
fi
