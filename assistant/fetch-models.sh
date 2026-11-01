#!/bin/sh
# Lädt die Sprachmodelle des Assistenten (einmalig, ca. 700 MB):
#  - Vosk (Aktivierungswort „Computer“), deutsch, klein
#  - faster-whisper „small“ (versteht Befehle und Liedtitel)
#  - Piper-Stimmen (deutsch): Thorsten, Kerstin, Ramona, Eva, Karlsson
# Aufruf: fetch-models.sh <Zielordner> <Python des Assistenten>
set -eu
dst="${1:-/usr/share/creative-assistant/models}"
py="${2:-/usr/lib/creative-assistant/venv/bin/python3}"
mkdir -p "$dst/piper"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

if [ ! -d "$dst/vosk-de" ]; then
    echo "Lade Vosk (Aktivierungswort) …"
    curl -fsSL -o "$tmp/vosk.zip" https://alphacephei.com/vosk/models/vosk-model-small-de-0.15.zip
    (cd "$tmp" && python3 -c "import zipfile; zipfile.ZipFile('vosk.zip').extractall('.')")
    mv "$tmp/vosk-model-small-de-0.15" "$dst/vosk-de"
fi

if [ ! -f "$dst/whisper-small/model.bin" ]; then
    echo "Lade Whisper (Spracherkennung) …"
    "$py" - "$dst/whisper-small" <<'PY'
import sys
from huggingface_hub import snapshot_download
snapshot_download("Systran/faster-whisper-small", local_dir=sys.argv[1],
                  allow_patterns=["config.json", "model.bin", "tokenizer.json", "vocabulary.*", "preprocessor_config.json"])
PY
fi

base=https://huggingface.co/rhasspy/piper-voices/resolve/main/de/de_DE
for v in thorsten/medium kerstin/low ramona/low eva_k/x_low karlsson/low; do
    name="de_DE-$(echo "$v" | tr '/' '-')"
    if [ ! -f "$dst/piper/$name.onnx" ]; then
        echo "Lade Stimme $name …"
        curl -fsSL -o "$dst/piper/$name.onnx" "$base/$v/$name.onnx" || { rm -f "$dst/piper/$name.onnx"; continue; }
        curl -fsSL -o "$dst/piper/$name.onnx.json" "$base/$v/$name.onnx.json"
    fi
done
chmod -R a+rX "$dst"
echo "Modelle bereit in $dst"
