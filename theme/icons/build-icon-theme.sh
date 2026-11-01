#!/bin/sh
# Baut das Symbol-Design „Creative“: Die Creative-Symbole ersetzen die
# Original-Symbole der mitgelieferten Programme überall – im Startmenü,
# in der Taskleiste und oben in der Titelleiste der Fenster.
# Aufruf: build-icon-theme.sh <Ordner mit Creative-SVGs> <Zielordner>
set -eu
src="$1"; dst="$2"
here="$(dirname "$0")"
mkdir -p "$dst/apps/scalable"
rm -f "$dst"/apps/scalable/*.svg
cat > "$dst/index.theme" <<'THEME'
[Icon Theme]
Name=Creative
Comment=Symbole von Creative OS
Inherits=breeze-dark,breeze,hicolor
Directories=apps/scalable

[apps/scalable]
Size=48
MinSize=8
MaxSize=512
Type=Scalable
Context=Applications
THEME
grep -v '^#' "$here/mapping.txt" | while read -r icon names; do
    [ -n "$icon" ] || continue
    file="$src/$icon.svg"
    [ "$icon" = player ] && file="$src/media-app.svg"
    [ -f "$file" ] || { echo "fehlt: $file" >&2; continue; }
    for n in $names; do
        cp "$file" "$dst/apps/scalable/$n.svg"
    done
done
gtk-update-icon-cache -q -f "$dst" 2>/dev/null || true
