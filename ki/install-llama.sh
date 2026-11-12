#!/bin/sh
# Installiert den KI-Rechenteil (llama-server von llama.cpp, Vulkan-Fassung) nach
# /usr/lib/creative-ki/llama. Feste Version mit Prüfsumme.
# Vulkan läuft auf NVIDIA und AMD; ohne passende Grafikkarte rechnet der Prozessor.
set -eu
TAG=b12322
SHA256=2b44c0f29bc0a7228ce97b5105640a8a29a808a4ea945cfbaa1baa1f3694a8af
DEST="${1:-/usr/lib/creative-ki/llama}"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
curl -fsSL -o "$tmp/llama.tar.gz" \
    "https://github.com/ggml-org/llama.cpp/releases/download/$TAG/llama-$TAG-bin-ubuntu-vulkan-x64.tar.gz"
echo "$SHA256  $tmp/llama.tar.gz" | sha256sum -c -
mkdir -p "$tmp/x" "$DEST"
tar -xzf "$tmp/llama.tar.gz" -C "$tmp/x"
srv="$(find "$tmp/x" -type f -name llama-server | head -1)"
[ -n "$srv" ] || { echo "llama-server fehlt im Paket" >&2; exit 1; }
cp "$srv" "$DEST/"
# Bibliotheken (libllama, libggml-*) aus dem ganzen Paket
find "$tmp/x" -name '*.so*' \( -type f -o -type l \) -exec cp -a {} "$DEST/" \;
find "$tmp/x" -iname 'LICENSE*' -type f -exec cp {} "$DEST/" \; 2>/dev/null || true
chmod -R a+rX "$DEST"
LD_LIBRARY_PATH="$DEST" "$DEST/llama-server" --version
