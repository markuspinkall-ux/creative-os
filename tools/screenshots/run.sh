#!/bin/sh
# Fotografiert alle Creative-Apps im fertigen Abbild (ohne Bildschirm, ohne Netz).
# Aufruf im Container:  sh /tools/run.sh /out
out="${1:-/out}"
mkdir -p "$out"
XDG_RUNTIME_DIR="$(mktemp -d)"
export XDG_RUNTIME_DIR HOME="$XDG_RUNTIME_DIR" LANG=de_DE.UTF-8
export QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software
export PYTHONPATH="/tools${PYTHONPATH:+:$PYTHONPATH}"
export CREATIVE3D_NO_WEB=1 CREATIVE_MAIL_NO_WEBENGINE=1 QTWEBENGINE_DISABLE_SANDBOX=1

shot() {   # shot <name> <programm> [argumente …]
    name="$1"; shift
    [ -x "$1" ] || { echo "– $name: $1 fehlt"; return 0; }
    CREATIVE_SCREENSHOT="$out/$name.png" timeout 25 "$@" >"$out/$name.log" 2>&1
    if [ -s "$out/$name.png" ]; then echo "✓ $name"; else echo "::warning::$name: kein Bildschirmfoto"; tail -5 "$out/$name.log"; fi
}

for page in network displays sound look updates system server backup; do
    shot "einstellungen-$page" /usr/bin/creative-settings --page "$page"
done
shot "einstellungen-neuerungen" /usr/bin/creative-settings --neuerungen
for app in art writer cut ftp 3d software notes mail claude iso broadcast pictures \
           taskmanager magazin podcast player calculator welcome files obs; do
    bin="/usr/bin/creative-$app"
    [ -x "$bin" ] || bin="/usr/lib/creative-$app/creative-$app"
    shot "$app" "$bin"
done
python3 /tools/contact.py "$out"
