#!/bin/sh
# Installiert die Sprachausgabe für den KI-Helfer: Piper (MIT-Lizenz, läuft offline) nach
# /usr/lib/creative-ki/piper und die mitgelieferte Stimme „Thorsten“ nach /usr/lib/creative-ki/stimmen.
# Feste Version, jede Datei mit Prüfsumme (siehe stimmen.json).
set -eu
TAG=2023.11.14-2
SHA256=a50cb45f355b7af1f6d758c1b360717877ba0a398cc8cbe6d2a7a3a26e225992
LIB="${1:-/usr/lib/creative-ki}"
LISTE="${2:-$LIB/stimmen.json}"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
curl -fsSL -o "$tmp/piper.tar.gz" "https://github.com/rhasspy/piper/releases/download/$TAG/piper_linux_x86_64.tar.gz"
echo "$SHA256  $tmp/piper.tar.gz" | sha256sum -c -
mkdir -p "$LIB/piper" "$LIB/stimmen"
tar -xzf "$tmp/piper.tar.gz" -C "$tmp"
cp -a "$tmp/piper/." "$LIB/piper/"
chmod -R a+rX "$LIB/piper"
# Mitgelieferte Stimmen (in stimmen.json „mitgeliefert“: true)
python3 - "$LISTE" "$LIB/stimmen" <<'PY'
import hashlib, json, sys, urllib.request
liste, ziel = sys.argv[1], sys.argv[2]
for key, info in json.load(open(liste, encoding="utf-8")).items():
    if not info.get("mitgeliefert"):
        continue
    for d in info["dateien"]:
        data = urllib.request.urlopen(urllib.request.Request(d["url"], headers={"User-Agent": "CreativeOS"}), timeout=300).read()
        if len(data) != d["groesse"] or hashlib.sha256(data).hexdigest() != d["sha256"]:
            sys.exit(f"Prüfsumme falsch: {d['datei']}")
        open(f"{ziel}/{d['datei']}", "wb").write(data)
        print("Stimme:", d["datei"])
PY
chmod -R a+rX "$LIB/stimmen"
echo "Hallo" | LD_LIBRARY_PATH="$LIB/piper" "$LIB/piper/piper" -q -m "$LIB/stimmen/de_DE-thorsten-medium.onnx" \
    --espeak_data "$LIB/piper/espeak-ng-data" --output_file "$tmp/probe.wav"
test -s "$tmp/probe.wav"
