#!/bin/sh
# Installiert den Sprachassistenten (Tray-Symbol kommt mit der Creative Shell).
set -eu
cd "$(dirname "$0")"
if [ "$(id -u)" -ne 0 ]; then
    echo "Bitte mit sudo ausführen: sudo ./install.sh"
    exit 1
fi

if [ "${SKIP_DNF:-0}" != 1 ]; then
    dnf install -y --skip-unavailable mpv yt-dlp espeak-ng sound-theme-freedesktop pulseaudio-utils \
        pipewire-utils python3-pip python3-numpy kf6-kded kded
fi

# Eigene Python-Umgebung für die Sprachmodelle (das System bleibt unberührt)
mkdir -p /usr/lib/creative-assistant
if [ ! -x /usr/lib/creative-assistant/venv/bin/python3 ]; then
    python3 -m venv --system-site-packages /usr/lib/creative-assistant/venv
fi
/usr/lib/creative-assistant/venv/bin/pip install --quiet --upgrade pip
/usr/lib/creative-assistant/venv/bin/pip install --quiet vosk faster-whisper piper-tts huggingface_hub

rm -rf /usr/lib/creative-assistant/creative_assistant
cp -r creative_assistant /usr/lib/creative-assistant/
find /usr/lib/creative-assistant/creative_assistant -name '__pycache__' -prune -exec rm -rf {} +
install -Dm755 bin/creative-assistant /usr/bin/creative-assistant

sh fetch-models.sh /usr/share/creative-assistant/models /usr/lib/creative-assistant/venv/bin/python3

echo "Fertig. Nach dem Neustart von Creative OS sitzt der Assistent im Tray (Mikrofon-Symbol)."
