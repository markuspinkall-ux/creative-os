#!/usr/bin/python3
"""Kommt das Bild der virtuellen „Gibeon Kamera“ (v4l2loopback, wie von Broadcast beschrieben)
in Studio an?  python3 tools/studio-virtualkamera-test.py /dev/videoN

Läuft in der Prüfung mit echtem v4l2loopback-Modul (exclusive_caps=1 wie im System) und einem
ffmpeg-Schreiber wie in Broadcast (yuv420p, erst 2 Bilder/s „Leerlauf“, dann volle Rate)."""
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "studio"))
from gibeon_studio import backend, engine, gst  # noqa: E402

dev = sys.argv[1]
gst.init()
devs = backend.video_devices()
print("Geräte:", [(d["node"], d["name"], d["virtual"]) for d in devs])
mine = next((d for d in devs if d["node"] == dev), None)
fails = []
if not mine:
    fails.append("virtuelle Kamera fehlt in der Geräteliste")
elif not mine["virtual"]:
    fails.append("virtuelle Kamera wird nicht als „Gibeon Kamera“ erkannt")

for green in (False, True):
    desc = engine.feeder_description({"type": "video", "device": mine["id"] if mine else dev, "green": green},
                                     1280, 720, 30)
    print("Pipeline:", desc)
    pipe = gst.launch(desc)
    sink = gst.bin_by_name(pipe, b"out")
    bus = gst.get_bus(pipe)
    count = [0]
    lock = threading.Lock()

    def on_sample(s):
        gst.pull_frame(s)
        with lock:
            count[0] += 1
        return gst.FLOW_OK

    gst.connect_new_sample(sink, on_sample)
    gst.set_state(pipe, gst.STATE_PLAYING)
    end = time.monotonic() + 8
    errors = []
    while time.monotonic() < end:
        m = gst.pop(bus)
        if m and m[0] == gst.MSG_ERROR:
            errors.append(f"{m[1]}: {m[2]}")
            break
        time.sleep(0.05)
    gst.set_state(pipe, gst.STATE_NULL)
    print(f"grün={green}: {count[0]} Bilder", "| Fehler:", errors or "keine")
    if count[0] < 10:
        fails.append(f"grün={green}: nur {count[0]} Bilder ({'; '.join(errors)})")

print("FEHLER:" if fails else "in Ordnung", *fails, sep="\n  ")
sys.exit(1 if fails else 0)
