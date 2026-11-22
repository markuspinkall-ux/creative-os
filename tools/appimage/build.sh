#!/bin/bash
# AppImages für andere Linux-Systeme bauen:
#   Gibeon-Studio-x86_64.AppImage   Studio (Aufnehmen und Streamen) samt Broadcast
#   Gibeon-3D-Studio-x86_64.AppImage 3D Studio (Foto → 3D-Figur, TRELLIS)
#
#   bash tools/appimage/build.sh <ausgabeordner> <version>
#
# Grundlage ist ein fertiges, verschiebbares Python von python-appimage (manylinux2014, läuft auf
# praktisch allen aktuellen Distributionen). Qt kommt mit PySide6 aus pip. GStreamer, PipeWire,
# v4l2loopback und podman nimmt das AppImage vom System – siehe README.md daneben.
set -euo pipefail
OUT="$(readlink -f "${1:-dist}")"
VERSION="${2:-$(date +%Y.%m.%d)}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
WORK="$(mktemp -d)"
PYVER=3.12
mkdir -p "$OUT"
cd "$WORK"

# ---- Werkzeuge ---------------------------------------------------------------------------------
echo "== Werkzeuge"
py_url=$(curl -fsSL "https://api.github.com/repos/niess/python-appimage/releases/tags/python$PYVER" \
  | python3 -c "import json,sys; a=[x['browser_download_url'] for x in json.load(sys.stdin)['assets'] if 'manylinux2014_x86_64' in x['name'] and x['name'].endswith('.AppImage')]; print(sorted(a)[-1])")
echo "Python: $py_url"
curl -fsSL -o python.AppImage "$py_url"
curl -fsSL -o appimagetool "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"
chmod +x python.AppImage appimagetool

# Neues AppDir mit Python
new_appdir() {
    rm -rf squashfs-root
    ./python.AppImage --appimage-extract >/dev/null
    rm -f squashfs-root/AppRun squashfs-root/*.desktop squashfs-root/*.png squashfs-root/*.svg squashfs-root/.DirIcon
    mv squashfs-root "$1"
}
pip_in() {   # pip_in <appdir> pakete…
    local d="$1"; shift
    "$d/opt/python$PYVER/bin/python$PYVER" -m pip install -q --no-warn-script-location --disable-pip-version-check "$@"
}
site_of() { echo "$1/opt/python$PYVER/lib/python$PYVER/site-packages"; }

# Teile von Qt, die keine der Apps braucht (spart gut 200 MB)
trim_qt() {
    local qt; qt="$(site_of "$1")/PySide6"
    rm -rf "$qt"/Qt/lib/libQt63D* "$qt"/Qt/lib/libQt6Quick3D* "$qt"/Qt/lib/libQt6Charts* \
           "$qt"/Qt/lib/libQt6DataVisualization* "$qt"/Qt/lib/libQt6Graphs* "$qt"/Qt/lib/libQt6Designer* \
           "$qt"/Qt/lib/libQt6Bluetooth* "$qt"/Qt/lib/libQt6Sensors* "$qt"/Qt/lib/libQt6SerialPort* \
           "$qt"/Qt/lib/libQt6Location* "$qt"/Qt/lib/libQt6Positioning* "$qt"/Qt/lib/libQt6RemoteObjects* \
           "$qt"/Qt/lib/libQt6Scxml* "$qt"/Qt/lib/libQt6SpatialAudio* "$qt"/Qt/lib/libQt6VirtualKeyboard* \
           "$qt"/Qt/qml/Qt3D "$qt"/Qt/qml/QtQuick3D "$qt"/Qt/qml/QtCharts "$qt"/Qt/qml/QtDataVisualization \
           "$qt"/Qt/qml/QtGraphs "$qt"/Qt/qml/QtLocation "$qt"/Qt/qml/QtPositioning "$qt"/Qt/qml/QtSensors \
           "$qt"/Qt/qml/QtScxml "$qt"/Qt/qml/QtRemoteObjects "$qt"/Qt/qml/QtQuick/VirtualKeyboard \
           "$qt"/designer "$qt"/assistant "$qt"/linguist "$qt"/lupdate "$qt"/Qt/translations/qt_help_* \
           "$qt"/examples "$qt"/glue "$qt"/include "$qt"/typesystems 2>/dev/null || true
    find "$qt" -name "Qt3D*.so" -o -name "QtCharts*.so" -o -name "QtDataVisualization*.so" -o -name "QtGraphs*.so" \
         -o -name "QtDesigner*.so" -o -name "QtBluetooth*.so" -o -name "QtSensors*.so" -o -name "QtQuick3D*.so" \
         -o -name "QtLocation*.so" -o -name "QtPositioning*.so" -o -name "QtScxml*.so" -o -name "QtRemoteObjects*.so" \
         | xargs -r rm -f
    find "$1" -name "__pycache__" -prune -exec rm -rf {} +
}

finish() {   # finish <appdir> <name> <desktop-id> <icon.svg>
    local d="$1" name="$2" id="$3" icon="$4"
    cp "$icon" "$d/$id.svg"
    rsvg-convert -w 256 -h 256 "$icon" -o "$d/$id.png"
    ln -sf "$id.png" "$d/.DirIcon"
    mkdir -p "$d/usr/share/gibeon-appimage"
    printf '{"app": "%s", "version": "%s"}\n' "$id" "$VERSION" > "$d/usr/share/gibeon-appimage/version.json"
    chmod +x "$d/AppRun"
    ARCH=x86_64 ./appimagetool --no-appstream -n "$d" "$OUT/$name-x86_64.AppImage" >/dev/null
    ls -la "$OUT/$name-x86_64.AppImage"
}

# =================================================================================================
# 1) Studio + Broadcast
# =================================================================================================
echo "== Studio + Broadcast"
A="$WORK/studio.AppDir"
new_appdir "$A"
pip_in "$A" "PySide6==6.8.*" numpy opencv-python-headless onnxruntime pillow
# Bildschirmfreigabe (xdg-desktop-portal): dbus-python, gebaut gegen die libdbus/libglib des Systems
pip_in "$A" dbus-python || echo "::warning::dbus-python ließ sich nicht bauen – Bildschirmfreigabe fehlt"
trim_qt "$A"
L="$A/usr/lib"
mkdir -p "$L/gibeon-studio" "$L/creative-broadcast" "$L/creative-shell/creative_shell/qml" \
         "$A/usr/share/creative-broadcast" "$L/ladspa" "$A/usr/bin"
cp -r "$ROOT/studio/gibeon_studio" "$L/gibeon-studio/"
cp "$ROOT/studio/dienste.json" "$L/gibeon-studio/" 2>/dev/null || true
cp -r "$ROOT/broadcast/creative_broadcast" "$L/creative-broadcast/"
cp -r "$ROOT/shell/creative_shell/qml/Creative" "$L/creative-shell/creative_shell/qml/"
cp "$ROOT/shell/creative_shell/look.py" "$(site_of "$A")/creative_look.py"
cp "$ROOT/dialogs/creative_dialogs.py" "$(site_of "$A")/creative_dialogs.py"
# KI-Modelle von Broadcast (wie im System-Abbild)
curl -fsSL -o "$A/usr/share/creative-broadcast/rvm_mobilenetv3_fp32.onnx" \
    https://github.com/PeterL1n/RobustVideoMatting/releases/download/v1.0.0/rvm_mobilenetv3_fp32.onnx
curl -fsSL -o "$A/usr/share/creative-broadcast/2xNomosUni_span_multijpg_fp16.onnx" \
    https://github.com/Phhofm/models/releases/download/2xNomosUni_span_multijpg/2xNomosUni_span_multijpg_fp16_opset17.onnx
# Rauschfilter DeepFilterNet als LADSPA-Filter für PipeWire
if [ -n "${DEEPFILTER_SO:-}" ] && [ -f "$DEEPFILTER_SO" ]; then
    cp "$DEEPFILTER_SO" "$L/ladspa/libdeep_filter_ladspa.so"
else
    echo "::warning::DeepFilterNet fehlt – Broadcast nimmt dann den einfacheren WebRTC-Filter"
fi
# kleine Startbefehle, damit Studio und Broadcast sich gegenseitig finden
for cmd in creative-broadcast:--broadcast creative-broadcastd:--broadcastd gibeon-studio:; do
    name="${cmd%%:*}"; arg="${cmd#*:}"
    printf '#!/bin/sh\nexec "$APPDIR/AppRun" %s "$@"\n' "$arg" > "$A/usr/bin/$name"
    chmod +x "$A/usr/bin/$name"
done
cat > "$A/AppRun" <<'EOF'
#!/bin/sh
# Gibeon Studio (mit Broadcast) als AppImage
HERE="$(dirname "$(readlink -f "$0")")"
export APPDIR="${APPDIR:-$HERE}"
export GIBEON_PREFIX="$HERE/usr" GIBEON_APPIMAGE=studio
export PATH="$HERE/usr/bin:$PATH"
export PYTHONPATH="$HERE/usr/lib/gibeon-studio:$HERE/usr/lib/creative-broadcast${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONNOUSERSITE=1 QTWEBENGINE_DISABLE_SANDBOX="${QTWEBENGINE_DISABLE_SANDBOX:-1}"
PY="$HERE/opt/python3.12/bin/python3.12"
case "${1:-}" in
    --broadcast)  shift; exec "$PY" -m creative_broadcast "$@" ;;
    --broadcastd) shift; exec "$PY" -m creative_broadcast.daemon "$@" ;;
    *)            exec "$PY" -m gibeon_studio "$@" ;;
esac
EOF
cat > "$A/gibeon-studio.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=Gibeon Studio
GenericName=Aufnehmen und Streamen
Comment=Aufnehmen und live streamen – mit Broadcast für Mikrofon und Kamera (aus Gibeon OS)
Exec=AppRun
Icon=gibeon-studio
Categories=AudioVideo;Video;Recorder;
Terminal=false
Actions=Broadcast;

[Desktop Action Broadcast]
Name=Broadcast (Mikrofon und Kamera)
Exec=AppRun --broadcast
EOF
finish "$A" Gibeon-Studio gibeon-studio "$ROOT/studio/gibeon-studio.svg"

# =================================================================================================
# 2) 3D Studio
# =================================================================================================
echo "== 3D Studio"
B="$WORK/3d.AppDir"
new_appdir "$B"
pip_in "$B" "PySide6==6.8.*" numpy pillow
trim_qt "$B"
D="$B/usr/lib/creative-3d"
mkdir -p "$D"
cp "$ROOT/creative3d/creative-3d" "$ROOT/creative3d/creative3d-setup" "$D/"
cp "$ROOT"/creative3d/viewer.html "$ROOT"/creative3d/creative3d_*.py "$ROOT/creative3d/dinov2_from_timm.py" "$D/"
cp "$ROOT/creative3d/trellis/run.py" "$D/trellis-run.py"
cp "$ROOT/creative3d/trellis/foto_projektion.py" "$D/trellis-foto_projektion.py"
cp "$ROOT/creative3d/trellis2/run2.py" "$D/trellis2-run2.py"
curl -fsSL -o "$D/model-viewer.min.js" https://cdn.jsdelivr.net/npm/@google/model-viewer@4.1.0/dist/model-viewer.min.js
chmod +x "$D/creative-3d" "$D/creative3d-setup"
cp "$ROOT/shell/creative_shell/look.py" "$(site_of "$B")/creative_look.py"
cp "$ROOT/dialogs/creative_dialogs.py" "$(site_of "$B")/creative_dialogs.py"
cat > "$B/AppRun" <<'EOF'
#!/bin/sh
# 3D Studio (aus Gibeon OS) als AppImage – TRELLIS läuft per podman auf der NVIDIA-Karte
HERE="$(dirname "$(readlink -f "$0")")"
export APPDIR="${APPDIR:-$HERE}"
export GIBEON_PREFIX="$HERE/usr" GIBEON_APPIMAGE=3d
export PYTHONNOUSERSITE=1 QTWEBENGINE_DISABLE_SANDBOX="${QTWEBENGINE_DISABLE_SANDBOX:-1}"
exec "$HERE/opt/python3.12/bin/python3.12" "$HERE/usr/lib/creative-3d/creative-3d" "$@"
EOF
cat > "$B/gibeon-3d-studio.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=3D Studio
GenericName=Foto zu 3D-Figur
Comment=Aus einem Foto wird eine 3D-Figur – lokal auf der NVIDIA-Grafikkarte (aus Gibeon OS)
Exec=AppRun
Icon=gibeon-3d-studio
Categories=Graphics;3DGraphics;
Terminal=false
EOF
finish "$B" Gibeon-3D-Studio gibeon-3d-studio "$ROOT/creative3d/creative-3d.svg"

echo "== fertig: $OUT"
