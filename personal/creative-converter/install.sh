#!/bin/sh
# Creative Converter – persönliche App (nicht Teil der Creative-OS-Releases).
# Installiert nur in deinen Benutzerordner, ohne sudo:
#   ~/.local/share/creative-converter/   App + eigenes yt-dlp
#   ~/.local/share/applications/         Startmenü-Eintrag
#
#   sh install.sh             installieren / aktualisieren
#   sh install.sh --entfernen wieder entfernen
set -eu
BRANCH="persoenlich-converter"
RAW="https://raw.githubusercontent.com/markuspinkall-ux/creative-os/$BRANCH/personal/creative-converter"
APP="$HOME/.local/share/creative-converter"
DESKTOP="$HOME/.local/share/applications/creative-converter.desktop"
ICON="$HOME/.local/share/icons/hicolor/scalable/apps/creative-converter.svg"

if [ "${1:-}" = "--entfernen" ]; then
    rm -rf "$APP" "$DESKTOP" "$ICON"
    echo "Creative Converter entfernt. Deine MP3-Dateien bleiben, wo sie sind."
    exit 0
fi

mkdir -p "$APP" "$(dirname "$DESKTOP")" "$(dirname "$ICON")"
here="$(cd "$(dirname "$0")" 2>/dev/null && pwd || echo "")"
fetch() {   # Datei aus dem Ordner neben install.sh nehmen, sonst von GitHub laden
    if [ -n "$here" ] && [ -f "$here/$1" ]; then cp "$here/$1" "$2"
    else curl -fsSL "$RAW/$1" -o "$2"; fi
}
echo "Lade Creative Converter …"
fetch creative-converter "$APP/creative-converter"
fetch creative-converter.svg "$ICON"
chmod 755 "$APP/creative-converter"

echo "Lade yt-dlp (offizielle Version von GitHub) …"
curl -fsSL "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp" -o "$APP/yt-dlp.neu"
chmod 755 "$APP/yt-dlp.neu"
mv "$APP/yt-dlp.neu" "$APP/yt-dlp"

command -v ffmpeg >/dev/null 2>&1 || echo "Hinweis: ffmpeg fehlt – ohne ffmpeg gibt es keine MP3."

cat > "$DESKTOP" <<DESK
[Desktop Entry]
Type=Application
Name=Creative Converter
GenericName=YouTube zu MP3
Comment=YouTube-Videos als MP3 speichern
Exec=$APP/creative-converter
Icon=creative-converter
Terminal=false
Categories=AudioVideo;Audio;
Keywords=YouTube;MP3;Musik;Konverter;Download;
DESK
update-desktop-database -q "$(dirname "$DESKTOP")" 2>/dev/null || true
gtk-update-icon-cache -q "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
echo "Fertig. Creative Converter steht jetzt im Startmenü."
