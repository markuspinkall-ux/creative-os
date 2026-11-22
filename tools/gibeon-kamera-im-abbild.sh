#!/bin/bash
# Läuft IM fertigen Gibeon-OS-Abbild (podman) – genau wie auf dem PC:
# Broadcast-Dienst starten, Kamera einschalten wie Studio es tut, dann die Gibeon Kamera lesen
# (wie Studio: GStreamer v4l2src, zusätzlich ffmpeg) und prüfen, ob echtes Bild ankommt.
set -u
OUT=/out
mkdir -p "$OUT"
export HOME=/tmp/home XDG_CONFIG_HOME=/tmp/home/.config XDG_RUNTIME_DIR=/tmp/run
mkdir -p "$XDG_CONFIG_HOME/creative-os" "$XDG_RUNTIME_DIR"; chmod 700 "$XDG_RUNTIME_DIR"
log() { echo "== $*"; }

log "Geräte"
for d in /sys/class/video4linux/video*; do echo "$d: $(cat $d/name) index=$(cat $d/index)"; done
log "Python-Bausteine"
PYTHONPATH=/usr/lib/creative-broadcast python3 - <<'PY' 2>&1
import sys
from creative_broadcast import daemon as d
print("loopback:", d.loopback_device())
print("kameras:", d.list_cameras())
print("modell da:", d.MODEL.exists())
for mod in ("numpy", "cv2", "onnxruntime"):
    try:
        m = __import__(mod); print(mod, getattr(m, "__version__", "?"), getattr(m, "__file__", ""))
    except Exception as e:
        print(mod, "FEHLER", repr(e))
try:
    m = d.Matting("sparsam"); print("matting ok:", m.engine)
except Exception as e:
    import traceback; traceback.print_exc()
PY

# Was Studio beim Hinzufügen der Gibeon Kamera tut (broadcast_camera)
PYTHONPATH=/usr/lib/gibeon-studio python3 - <<'PY' 2>&1 || true
try:
    from gibeon_studio import backend
    print("broadcast_camera():", backend.broadcast_camera())
except Exception as e:
    print("Studio-Backend nicht importierbar:", repr(e))
    import json, os
    p = os.path.expanduser("~/.config/creative-os/broadcast.json")
    json.dump({"camera": True, "effect": "green"}, open(p, "w"))
PY
cat "$XDG_CONFIG_HOME/creative-os/broadcast.json"; echo
pgrep -f creative_broadcast.daemon >/dev/null || (creative-broadcastd >"$OUT/daemon.log" 2>&1 &)
sleep 8
log "Status vor dem Zuschauen"; cat "$XDG_RUNTIME_DIR/creative-broadcast/status.json"; echo
DEV=$(PYTHONPATH=/usr/lib/creative-broadcast python3 -c "from creative_broadcast import daemon as d; print(d.loopback_device() or '')")
echo "Gibeon Kamera: $DEV"
v4l2-ctl -d "$DEV" --all 2>/dev/null | head -30 || true

log "Zuschauen wie Studio (GStreamer v4l2src ! decodebin)"
if command -v gst-launch-1.0 >/dev/null; then
  timeout 40 gst-launch-1.0 -q v4l2src device="$DEV" do-timestamp=true num-buffers=400 ! decodebin ! videoconvert ! \
    videorate ! video/x-raw,framerate=2/1 ! jpegenc ! multifilesink location="$OUT/gst-%03d.jpg" >"$OUT/gst.log" 2>&1 &
  GST=$!
else
  echo "kein gst-launch im Abbild – Studios Weg über Python/GStreamer"
  timeout 40 python3 - "$DEV" "$OUT" >"$OUT/gst.log" 2>&1 <<'PY' &
import sys, gi
gi.require_version("Gst", "1.0"); from gi.repository import Gst
Gst.init(None)
p = Gst.parse_launch(f"v4l2src device={sys.argv[1]} do-timestamp=true num-buffers=400 ! decodebin ! videoconvert ! videorate ! video/x-raw,framerate=2/1 ! jpegenc ! multifilesink location={sys.argv[2]}/gst-%03d.jpg")
p.set_state(Gst.State.PLAYING)
msg = p.get_bus().timed_pop_filtered(38 * Gst.SECOND, Gst.MessageType.ERROR | Gst.MessageType.EOS)
print("Ende:", msg.type if msg else "Zeit", msg.parse_error() if msg and msg.type == Gst.MessageType.ERROR else "")
p.set_state(Gst.State.NULL)
PY
  GST=$!
fi
for i in 1 2 3 4 5 6 7; do sleep 4; echo "t=$((i*4))s: $(cat $XDG_RUNTIME_DIR/creative-broadcast/status.json)"; done
wait $GST; echo "gst exit=$?"; cat "$OUT/gst.log" | tail -5
ls "$OUT" | head -50

log "Auswertung"
python3 - "$OUT" <<'PY'
import sys, glob, json, os
import cv2, numpy as np
out = sys.argv[1]
files = sorted(glob.glob(f"{out}/gst-*.jpg"))
res = {"bilder": len(files)}
if files:
    last = cv2.imread(files[-1]); res["groesse"] = list(last.shape)
    mean = last.reshape(-1, 3).mean(0).tolist(); res["mittel_bgr"] = [round(x) for x in mean]
    graphit = np.abs(last.astype(int) - np.array([34, 27, 21])).sum(2) < 30
    res["anteil_graphit"] = round(float(graphit.mean()), 3)
    cv2.imwrite(f"{out}/letztes-bild.png", last)
st = json.load(open(os.environ["XDG_RUNTIME_DIR"] + "/creative-broadcast/status.json"))
res["status"] = st
print(json.dumps(res, indent=1, ensure_ascii=False))
ok = res["bilder"] > 5 and res.get("anteil_graphit", 1) < 0.9 and str(st.get("camera")) == "aktiv"
print("GIBEON KAMERA:", "OK" if ok else "FEHLER")
json.dump(res, open(f"{out}/ergebnis.json", "w"), indent=1, ensure_ascii=False)
sys.exit(0 if ok else 1)
PY
