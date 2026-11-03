#!/bin/bash
# Mehrere Monitore prüfen: KWin mit 3 virtuellen Bildschirmen, Shell starten,
# dann ausgeben, auf welchem Bildschirm Leisten und Hintergründe landen.
set +e
img=ghcr.io/markuspinkall-ux/creative-os:amd-testing
sudo podman pull -q "$img" >/dev/null
sudo podman run --rm -v "$PWD:/src:ro" "$img" bash -c '
useradd -m t >/dev/null 2>&1; cp /usr/bin/kwin_wayland /tmp/kwin; chmod 755 /tmp/kwin  # Kopie ohne Datei-Fähigkeiten
cat > /tmp/dump.js <<JS
for (const o of workspace.screens) console.info("SCREEN", o.name, o.geometry.x, o.geometry.y, o.geometry.width, o.geometry.height);
for (const w of workspace.stackingOrder) console.info("WIN", JSON.stringify(w.caption), "out=" + (w.output ? w.output.name : "?"), w.x, w.y, w.width, w.height);
JS
chmod 644 /tmp/dump.js
cat > /tmp/inner.sh <<SH
export XDG_RUNTIME_DIR=/tmp/xdg-t; mkdir -p -m700 \$XDG_RUNTIME_DIR
export QT_LOGGING_RULES="kwin_scripting=true;js=true;qml=true"
/tmp/kwin --virtual --no-lockscreen --output-count 3 --width 1280 --height 720 --socket wayland-9 > /tmp/kwin-\$1.log 2>&1 &
sleep 8
export WAYLAND_DISPLAY=wayland-9 QT_QPA_PLATFORM=wayland
if [ "\$1" = repo ]; then export PYTHONPATH=/src/shell; else export PYTHONPATH=/usr/lib/creative-shell; fi
python3 -m creative_shell > /tmp/shell-\$1.log 2>&1 &
sleep 18
id=\$(gdbus call --session --dest org.kde.KWin --object-path /Scripting --method org.kde.kwin.Scripting.loadScript /tmp/dump.js dump\$1 | grep -o "[0-9]\+" | head -1)
gdbus call --session --dest org.kde.KWin --object-path /Scripting/Script\$id --method org.kde.kwin.Script.run >/dev/null
sleep 3
echo "######## \$1"; grep -o "\(SCREEN\|WIN\) .*" /tmp/kwin-\$1.log
echo "--- kwin log"; tail -15 /tmp/kwin-\$1.log
echo "--- shell log"; grep -v "^\$" /tmp/shell-\$1.log | grep -iv "fontconfig" | head -25
kill %2 %1 2>/dev/null; sleep 2
SH
chmod 755 /tmp/inner.sh
for v in image repo; do su t -c "dbus-run-session -- bash /tmp/inner.sh $v"; done
'
