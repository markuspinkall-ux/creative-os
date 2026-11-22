#!/usr/bin/python3
"""Studio prüfen und fotografieren (ohne Kamera/Bildschirm: Testbilder).

  python3 tools/studio-vorschau.py ausgabe.png [graphit|porzellan]

Prüft Szenen, Bilder, Verschieben/Skalieren und die Vorschau und macht ein Foto der Oberfläche
mit ausgewählter Quelle (Griffe an den Ecken sichtbar)."""

import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "studio"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
tmp = tempfile.mkdtemp()
os.environ["XDG_CONFIG_HOME"] = tmp
os.environ["XDG_CACHE_HOME"] = tmp
design = sys.argv[2] if len(sys.argv) > 2 else "graphit"
(Path(tmp) / "creative-os").mkdir(parents=True, exist_ok=True)
(Path(tmp) / "creative-os" / "look.conf").write_text(f"design={design}\n")

from PySide6.QtCore import QTimer, QUrl  # noqa: E402
from PySide6.QtGui import QColor, QGuiApplication, QImage  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine, qmlRegisterType  # noqa: E402
from PySide6.QtQuickControls2 import QQuickStyle  # noqa: E402

QQuickStyle.setStyle("Basic")
app = QGuiApplication(sys.argv[:1])
from gibeon_studio import backend  # noqa: E402

fails = []


def check(ok, text):
    print(("ok    " if ok else "FEHLT ") + text)
    if not ok:
        fails.append(text)


# ---- Umzug alter Einstellungen -------------------------------------------------------------------
old = backend.merge(backend.DEFAULTS, {"main": {"type": "screen"}, "cam": {"on": True, "device": "/dev/video0",
                                                                             "corner": "oben-links", "size": "klein"}})
backend.migrate(old)
items = old["scenes"][0]["items"]
check([i["kind"] for i in items] == ["screen", "camera"] and items[1]["round"] and items[1]["x"] < 0.1,
      "alte Einstellungen → Szene 1 mit Bildschirm und abgerundeter Kamera oben links")

# ---- Studio mit Testquellen ---------------------------------------------------------------------
s = backend.Studio(selftest=True)
img = QImage(400, 200, QImage.Format.Format_ARGB32)
img.fill(QColor("#f2c94c"))
png = os.path.join(tmp, "logo.png")
img.save(png)
pos = s.addImage(png)
check(pos == 2, "Bild eingefügt")
it = s.cfg["scenes"][0]["items"][2]
check(abs(it["aspect"] - 2.0) < 0.01, "Seitenverhältnis des Bildes übernommen")
s.moveItem(2, 0.04, 0.06, 0.25)
check(abs(backend.item_height(it) - 0.25 * 16 / 9 / 2) < 1e-6, "Skalieren bleibt proportional")
s._rebuild()
t0 = time.time()
while s.mixer.frame() is None and time.time() - t0 < 8:
    time.sleep(0.1)
print(f"  erstes Bild nach {time.time() - t0:.1f} s")
f = s.mixer.frame()
check(f is not None, "Vorschau liefert Bilder")
if f is None:
    print("  Fehler:", s.error, s.mixer.errors, "Pads:", s.mixer.pads, "Pipeline:", bool(s.mixer.pipe))
    sources, audio = s._sources()
    print("  Quellen:", sources)
if f:
    d, w, h = f

    def px(fx, fy):
        i = (int(fy * h) * w + int(fx * w)) * 4
        return tuple(d[i:i + 3])
    b, g, r = px(0.04 + 0.12, 0.06 + 0.05)
    check(r > 200 and g > 160 and b < 120, f"Bild sitzt an der gewählten Stelle ({r},{g},{b})")
    s.moveItem(2, 0.6, 0.06, 0.25)
    time.sleep(0.4)
    d, w, h = s.mixer.frame()
    b, g, r = px(0.6 + 0.12, 0.06 + 0.05)
    check(r > 200 and g > 160 and b < 120, "Verschieben wirkt sofort (ohne Neuaufbau)")
    # Monitor-Anzeige: Kamera/Capture-Karte pur (ohne das Bild darüber) an einen anderen Monitor
    s.projectItem(1, "Monitor 2")
    time.sleep(0.8)
    pi = backend.PROJ._img
    check(not pi.isNull() and s._state()["projector"].get("screen") == "Monitor 2",
          f"Monitor-Anzeige bekommt Bilder ({pi.width()}×{pi.height()})")
    s.stopProjector()
    check(not s.projector, "Monitor-Anzeige beendet")
    # abgerundete Kamera: Ecke zeigt das Testbild darunter, Mitte die Kamera
s.set("audio.mic.muted", True)
s.addScene()
check(s.cfg["scene"] == 1 and s._layout()[0] == {}, "neue Szene ist leer")
s.set("audio.mic.muted", False)
s.setScene(0)
check(s.cfg["audio"]["mic"]["muted"] is True, "Szene merkt sich Stummschaltung")
s.setScene(1)
check(s.cfg["audio"]["mic"]["muted"] is False, "andere Szene, anderer Ton")
s.setScene(0)
check(len(s._layout()[0]) == 3, "Szenenwechsel zeigt wieder alle Quellen")
s.duplicateScene(0)
check(len(s.cfg["scenes"]) == 3 and s.cfg["scenes"][1]["name"].endswith("(Kopie)"), "Szene duplizieren")
s.removeScene(1)
s.removeScene(1)
check(len(s.cfg["scenes"]) == 1, "Szenen löschen")
check(backend.audio_outputs()[0]["name"] == "Standard-Ausgabe", "Desktop-Ton: Auswahl beginnt mit Standard-Ausgabe")
s.set("canvas", "1440p60")
s.set("stream_res", "936")
s.set("stream_fps", "30")
check(s._stream_size() == (1664, 936, 30), "Stream: 1440p60 → 936p30")
s.set("rec_quality", "hoch")
check(s._rec_kbps() > 20000, f"Aufnahme-Bitrate 1440p60 hoch: {s._rec_kbps()} kbit/s")
s.set("canvas", "1080p30")
bpos = s.addSource("browser")
s.setItem(bpos, "url", "data:text/html,<body style='margin:0;background:transparent'><div style='width:400px;height:300px;background:%23ff0000'></div></body>")
check(any(w["url"].startswith("data:") for w in s._web_sources()), "Browserquelle angelegt")
s.set("twitch_key", "live_123")
s.set("youtube_key", "abcd-efgh")
s.set("targets.kick", True)
s.set("kick_url", "rtmps://kick.example/app")
s.set("kick_key", "sk_1")
wanted = dict(s._wanted_targets())
check(wanted.get("twitch") == "rtmp://ingest.global-contribute.live-video.net/app/live_123"
      and wanted.get("youtube") == "rtmp://a.rtmp.youtube.com/live2/abcd-efgh"
      and wanted.get("kick") == "rtmps://kick.example/app/sk_1", "Multistream: Twitch/YouTube per Schlüssel + Kick")

# ---- Oberfläche --------------------------------------------------------------------------------
qmlRegisterType(backend.Preview, "Studio", 1, 0, "Preview")
qmlRegisterType(backend.ProjectorView, "Studio", 1, 0, "ProjectorView")
engine = QQmlApplicationEngine()
engine.addImportPath(str(ROOT / "shell" / "creative_shell" / "qml"))
engine.rootContext().setContextProperty("studio", s)
from gibeon_studio.appupdate import AppUpdate  # noqa: E402
KEEP_UPDATE = AppUpdate()
engine.rootContext().setContextProperty("appUpdate", KEEP_UPDATE)
engine.load(QUrl.fromLocalFile(str(ROOT / "studio" / "gibeon_studio" / "qml" / "Main.qml")))
check(bool(engine.rootObjects()), "Oberfläche lädt")
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(tmp, "studio.png")


def web_check():
    """Kommt die Browserquelle im Bild an? (Offscreen ohne Grafikkarte kann WebEngine fehlen.)"""
    it = next(i for i in s.cfg["scenes"][0]["items"] if i["kind"] == "browser")
    f = s.mixer.frame()
    if f:
        d, w, h = f
        x = int((it["x"] + it["w"] * 0.25) * w)
        y = int((it["y"] + backend.item_height(it) * 0.25) * h)
        b, g, r = d[(y * w + x) * 4:(y * w + x) * 4 + 3]
        print(f"Browserquelle im Bild: {'ja' if r > 200 and g < 60 else 'nein'} ({r},{g},{b})")


def shoot():
    web_check()
    if s.poll:
        print("Umfrage im Bild:", s.poll.state()["phase"], s.poll.state()["total"], "Stimmen")
    win = engine.rootObjects()[0]
    win.setProperty("selected", s.cfg["scenes"][0]["items"][1]["id"])
    from PySide6.QtCore import QObject

    def second():
        dlg = win.findChild(QObject, "settingsDialog")
        if dlg is not None:
            dlg.setProperty("tab", "ziele")
            dlg.setProperty("open", True)
        out2 = out.replace(".png", "-einstellungen.png")
        QTimer.singleShot(800, lambda: (win.grabWindow().save(out2), print("Foto:", out2), app.quit()))
    QTimer.singleShot(1200, lambda: (win.grabWindow().save(out), print("Foto:", out), second()))


if engine.rootObjects():
    s.startPoll("Welches Spiel spielen wir als Nächstes?", ["Mario Kart", "Zelda", "Tetris"], 120, 20, False)
    for i, v in enumerate("1121321112"):
        s.poll.vote(f"zuschauer{i}", v)
    check(s.poll.state()["total"] == 10 and any(i["kind"] == "umfrage" for i in s.cfg["scenes"][0]["items"]),
          "Umfrage gestartet, Einblendung in der Szene, Stimmen gezählt")
    s.addScene()
    s.renameScene(1, "Pause")
    s.setScene(0)
    QTimer.singleShot(5000, shoot)
    QTimer.singleShot(15000, app.quit)
    app.exec()
s.shutdown()
sys.exit(1 if fails else 0)
