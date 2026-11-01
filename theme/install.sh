#!/bin/sh
# Installiert das Creative-OS-Aussehen für alle Programme:
#  - Fensterrahmen „Creative Graphit“ (KWin)
#  - Graphit-Farben + Arial für Qt/KDE-Programme (kdeglobals)
#  - Graphit für GTK-Programme (z. B. Software)
#  - aufgeräumtes Startmenü mit Creative-Symbolen
# Alles gilt nur in der Creative-OS-Sitzung; Plasma bleibt unverändert.
set -eu
cd "$(dirname "$0")"

if [ "$(id -u)" -ne 0 ]; then
    echo "Bitte mit sudo ausführen: sudo ./install.sh"
    exit 1
fi

# Die mitgelieferten Standard-Apps (alles andere wird im Startmenü ausgeblendet)
[ "${SKIP_DNF:-0}" = 1 ] || dnf install -y --skip-unavailable plasma-breeze konsole gwenview spectacle ark \
    plasma-systemmonitor plasma-integration breeze-gtk breeze-icon-theme liberation-sans-fonts

XDG=/usr/share/creative-os/xdg
mkdir -p "$XDG" /usr/share/creative-os/gtk /usr/share/color-schemes

# Fensterrahmen
rm -rf /usr/share/aurorae/themes/CreativeGraphit
mkdir -p /usr/share/aurorae/themes
cp -r aurorae/CreativeGraphit /usr/share/aurorae/themes/

# Fensterrahmen wählen: Breeze (von KWin gezeichnet), sonst unser SVG-Rahmen
KWINRC="$XDG/kwinrc"
if [ -f "$KWINRC" ]; then
    sed -i '/^library=/d;/^theme=/d' "$KWINRC"
    if ls /usr/lib64/qt6/plugins/org.kde.kdecoration3/*breeze* >/dev/null 2>&1 \
       || ls /usr/lib/qt6/plugins/org.kde.kdecoration3/*breeze* >/dev/null 2>&1; then
        sed -i 's/^\[org.kde.kdecoration2\]$/[org.kde.kdecoration2]\nlibrary=org.kde.breeze\ntheme=Breeze/' "$KWINRC"
        echo "Fensterrahmen: Breeze in Graphit-Farben"
    else
        aur="$(ls /usr/lib64/qt6/plugins/org.kde.kdecoration3/ /usr/lib/qt6/plugins/org.kde.kdecoration3/ 2>/dev/null | grep -o 'org.kde.kwin.aurorae[.a-z0-9]*' | sort | tail -n1)"
        sed -i "s/^\[org.kde.kdecoration2\]\$/[org.kde.kdecoration2]\nlibrary=${aur:-org.kde.kwin.aurorae}\ntheme=__aurorae__svg__CreativeGraphit/" "$KWINRC"
        echo "Fensterrahmen: Creative Graphit (Breeze ist nicht installiert)"
    fi
fi

# Breeze-Rahmen-Einstellungen (runde Ecken, großer weicher Schatten, keine Trennlinie)
install -Dm644 breezerc "$XDG/breezerc"

# Farben und Schrift
install -Dm644 kdeglobals "$XDG/kdeglobals"
install -Dm644 CreativeGraphit.colors /usr/share/color-schemes/CreativeGraphit.colors

# GTK
install -Dm644 gtk/gtk-3.0/settings.ini "$XDG/gtk-3.0/settings.ini"
install -Dm644 gtk/gtk-4.0/settings.ini "$XDG/gtk-4.0/settings.ini"
install -Dm644 gtk/gtk.css /usr/share/creative-os/gtk/gtk.css
# KDE soll die GTK-Einstellungen nicht mit eigenen Farben überschreiben
mkdir -p /etc/xdg
cat > /etc/xdg/kded6rc <<'KDED'
[Module-gtkconfig]
autoload=false
KDED
install -Dm755 apps/creative-theme-user /usr/libexec/creative-theme-user

# Creative-Symbole für die mitgelieferten Apps
ICONS="${CREATIVE_ICONS:-../shell/creative_shell/qml/Creative/icons}"
for pair in settings:settings browser:browser games:games chat:chat store:store terminal:terminal \
            editor:editor image:image calculator:calculator screenshot:screenshot \
            taskmanager:taskmanager files:files player:media-app drive:drive notes:notes shots:shots pictures:pictures; do
    name="${pair%%:*}"; file="${pair#*:}"
    install -Dm644 "$ICONS/$file.svg" "/usr/share/icons/hicolor/scalable/apps/creative-$name.svg"
done
gtk-update-icon-cache -q /usr/share/icons/hicolor 2>/dev/null || true

# Symbol-Design „Creative“: ersetzt die Original-Symbole der Standard-Apps
# auch in Titelleiste und Taskleiste (z. B. Rechner, Terminal, Steam)
sh icons/build-icon-theme.sh "$ICONS" /usr/share/icons/Creative

# Startmenü aufräumen
install -Dm755 apps/creative-apps-sync /usr/bin/creative-apps-sync
creative-apps-sync

echo
echo "Fertig. Bitte Creative OS einmal neu starten (abmelden und wieder anmelden)."
