#!/bin/sh
set -eu

install_package() {
    rm -rf "$2"
    mkdir -p "$2"
    cp -R "$1/." "$2/"
}

install_launcher() {
    install -Dm755 "$1" "/usr/bin/$2"
    install -Dm644 "$3" "/usr/share/applications/$2.desktop"
    install -Dm644 "$4" "/usr/share/icons/hicolor/scalable/apps/$2.svg"
}

install_package /src/art/creative_art /usr/lib/creative-art/creative_art
install_launcher /src/art/creative-art creative-art /src/art/creative-art.desktop /src/art/creative-art.svg
install_launcher /src/writer/creative-writer creative-writer /src/writer/creative-writer.desktop /src/writer/creative-writer.svg
install_package /src/podcast/creative_podcast /usr/lib/creative-podcast/creative_podcast
install_launcher /src/podcast/bin/creative-podcast creative-podcast /src/podcast/creative-podcast.desktop /src/podcast/creative-podcast.svg
install_package /src/settings/creative_settings /usr/lib/creative-settings/creative_settings
install -Dm755 /src/theme/apps/creative-apps-sync /usr/bin/creative-apps-sync
creative-apps-sync
