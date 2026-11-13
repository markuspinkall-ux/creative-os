#!/bin/bash
# Brave im Graphit-Look fotografieren: zwei Tabs, Maus über dem inaktiven Tab (Hover + Vorschaukarte).
#   tools/brave-foto.sh <ausgabe-ordner> [css-datei]
set -u
out="$1"; css="${2:-theme/gtk/gtk.css}"
mkdir -p "$out"
H=$(mktemp -d); export HOME="$H" XDG_CONFIG_HOME="$H/.config"
mkdir -p "$XDG_CONFIG_HOME/gtk-3.0" "$XDG_CONFIG_HOME/gtk-4.0"
cp theme/gtk/gtk-3.0/settings.ini "$XDG_CONFIG_HOME/gtk-3.0/settings.ini"
cp "$css" "$XDG_CONFIG_HOME/gtk-3.0/gtk.css"; cp "$css" "$XDG_CONFIG_HOME/gtk-4.0/gtk.css"
prof="$XDG_CONFIG_HOME/BraveSoftware/Brave-Browser"; mkdir -p "$prof/Default"
echo '{"extensions":{"theme":{"system_theme":1}},"browser":{"theme":{}},"brave":{"tabs":{"vertical_tabs_enabled":false}}}' > "$prof/Default/Preferences"
echo '{}' > "$prof/Local State"
Xvfb :9 -screen 0 1280x800x24 >/dev/null 2>&1 & xv=$!
export DISPLAY=:9
sleep 2
p1="data:text/html,<title>YouTube</title><body style='background:%2314161b;color:white'>Seite 1</body>"
p2="data:text/html,<title>Neuer Tab</title><body style='background:%2314161b;color:white'>Seite 2</body>"
brave-browser --no-sandbox --no-first-run --disable-gpu --user-data-dir="$prof" --window-size=1280,800 --window-position=0,0 \
    "$p1" "$p2" >/tmp/brave.log 2>&1 & bp=$!
sleep 12
import -window root "$out/brave-ruhe.png"
# Maus über den ersten (inaktiven) Tab
xdotool mousemove 120 20; sleep 3
import -window root "$out/brave-hover.png"
convert "$out/brave-hover.png" -crop 640x220+0+0 +repage "$out/brave-hover-ausschnitt.png"
kill $bp $xv 2>/dev/null
tail -5 /tmp/brave.log
