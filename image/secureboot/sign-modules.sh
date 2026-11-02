#!/bin/bash
# Selbst gebaute Kernelmodule (NVIDIA, virtuelle Kamera) für Secure Boot signieren.
# Der private Schlüssel kommt nur während des Bauens als Build-Geheimnis herein
# (/run/secrets/mokkey) und landet nie im Abbild. Ohne Schlüssel: nichts tun.
# Aufruf: sign-modules.sh <kernelversion> <modulname-muster>
set -u
KVER="$1"; PAT="$2"
KEY=/run/secrets/mokkey
CERT=/usr/share/creative-os/secureboot/creative-os-mok.der
SIGN="/usr/src/kernels/$KVER/scripts/sign-file"
if [ ! -s "$KEY" ]; then echo "Secure Boot: kein Signaturschlüssel – Module bleiben unsigniert"; exit 0; fi
[ -x "$SIGN" ] || { echo "SECURE BOOT: sign-file fehlt"; exit 0; }
# Vorhandene Signatur (z. B. von akmods mit Zufallsschlüssel) vorher entfernen
unsign() {
    python3 - "$1" <<'PY'
import struct, sys
p = sys.argv[1]
d = open(p, "rb").read()
magic = b"~Module signature appended~\n"
while d.endswith(magic):
    info = d[-len(magic) - 12:-len(magic)]
    sig_len = struct.unpack(">I", info[8:12])[0]
    d = d[:-len(magic) - 12 - sig_len]
open(p, "wb").write(d)
PY
}
signit() { unsign "$1" && "$SIGN" sha256 "$KEY" "$CERT" "$1"; }
n=0
while IFS= read -r m; do
    case "$m" in
        *.ko.xz)  xz -d -q "$m"; f="${m%.xz}";  signit "$f" && xz -q -f --check=crc32 "$f" ;;
        *.ko.zst) zstd -q -d --rm "$m"; f="${m%.zst}"; signit "$f" && zstd -q --rm "$f" ;;
        *.ko)     signit "$m" ;;
    esac && n=$((n + 1))
done < <(find "/usr/lib/modules/$KVER" -path "*extra*" \( -name "${PAT}.ko" -o -name "${PAT}.ko.xz" -o -name "${PAT}.ko.zst" \))
echo "Secure Boot: $n Module signiert ($PAT)"
m1=$(find "/usr/lib/modules/$KVER" -path "*extra*" -name "${PAT}.ko*" | head -1)
[ -n "$m1" ] && echo "Secure Boot: Signatur von $(basename "$m1"): $(modinfo -F signer "$m1" 2>/dev/null)"
