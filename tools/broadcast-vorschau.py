"""Creative Broadcast fotografieren, mit gespielten Messwerten (ohne Kamera/Grafikkarte).
   QT_QPA_PLATFORM=offscreen python3 tools/broadcast-vorschau.py <ausgabe.png> [graphit|porzellan] [langsam]"""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
design = sys.argv[2] if len(sys.argv) > 2 else "graphit"
slow = len(sys.argv) > 3 and sys.argv[3] == "langsam"
home = Path(tempfile.mkdtemp())
(home / ".config" / "creative-os").mkdir(parents=True)
(home / ".config" / "creative-os" / "look.conf").write_text(f"[Look]\ndesign={design}\naccent=blau\n")
os.environ["XDG_CONFIG_HOME"] = str(home / ".config")
os.environ["HOME"] = str(home)

from PySide6.QtCore import Property, QObject, QTimer, QUrl, Signal, Slot  # noqa: E402
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter, QLinearGradient  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402
from PySide6.QtQuickControls2 import QQuickStyle  # noqa: E402

# Vorschaubild: weicher Verlauf statt Kamera
prev = home / "preview.jpg"
img = QImage(640, 360, QImage.Format_RGB32)
p = QPainter(img)
g = QLinearGradient(0, 0, 640, 360)
g.setColorAt(0, QColor("#2b3a55"))
g.setColorAt(1, QColor("#121722"))
p.fillRect(img.rect(), g)
p.setBrush(QColor("#c9a48a"))
p.setPen(QColor("#c9a48a"))
p.drawEllipse(270, 90, 100, 120)
p.setBrush(QColor("#3c4f72"))
p.drawRoundedRect(210, 215, 220, 160, 60, 60)
p.end()
img.save(str(prev))


class Fake(QObject):
    changed = Signal()
    statusChanged = Signal()
    previewChanged = Signal()

    def __init__(self):
        super().__init__()
        self._up = "beste" if slow else "schnell"

    @Slot(str)
    def setUpscale(self, v):
        self._up = v
        self.changed.emit()

    for _n in ("setVoice", "setCamera", "setPreview"):
        locals()[_n] = Slot(bool)(lambda self, v: None)
    for _n in ("setVoiceInput", "setCameraDevice", "setEffect", "setBackground", "setQuality"):
        locals()[_n] = Slot(str)(lambda self, v: None)
    setStrength = Slot(int)(lambda self, v: None)
    refreshMicrophones = Slot()(lambda self: None)
    refreshCameras = Slot()(lambda self: None)

    voice = Property(bool, lambda s: True, constant=True)
    strength = Property(int, lambda s: 70, constant=True)
    camera = Property(bool, lambda s: True, constant=True)
    cameraDevice = Property(str, lambda s: "", constant=True)
    effect = Property(str, lambda s: "blur", constant=True)
    background = Property(str, lambda s: "", constant=True)
    backgroundUrl = Property(str, lambda s: "", constant=True)
    quality = Property(str, lambda s: "sparsam", constant=True)
    cameras = Property("QVariantList", lambda s: [{"device": "/dev/video0", "name": "HD Pro Webcam C920"}], constant=True)
    microphones = Property("QVariantList", lambda s: [], constant=True)
    voiceInput = Property(str, lambda s: "", constant=True)
    voiceStatus = Property(str, lambda s: "aktiv", constant=True)
    cameraStatus = Property(str, lambda s: "aktiv", constant=True)
    fps = Property(int, lambda s: 41 if slow else 60, constant=True)
    engine = Property(str, lambda s: "CUDA", constant=True)
    deepFilter = Property(bool, lambda s: True, constant=True)
    previewUrl = Property(str, lambda s: QUrl.fromLocalFile(str(prev)).toString(), constant=True)
    upscale = Property(str, lambda s: s._up, notify=changed)
    upscaleState = Property(str, lambda s: "aktiv", constant=True)
    upscaleMs = Property(float, lambda s: 19.4 if slow else 6.8, constant=True)
    processingMs = Property(float, lambda s: 4.9, constant=True)
    budgetMs = Property(float, lambda s: 16.7, constant=True)
    slow = Property(bool, lambda s: slow, constant=True)
    cameraMode = Property(str, lambda s: "1280×720 · 60 Bilder/s (MJPG)", constant=True)
    outputMode = Property(str, lambda s: "1920×1080 · 60 Bilder/s", constant=True)
    upscaleAvailable = Property(str, lambda s: "", constant=True)


QQuickStyle.setStyle("Basic")
app = QGuiApplication(sys.argv)
engine = QQmlApplicationEngine()
engine.addImportPath(str(ROOT / "shell" / "creative_shell" / "qml"))
fake = Fake()
engine.rootContext().setContextProperty("bc", fake)
engine.load(QUrl.fromLocalFile(str(ROOT / "broadcast" / "creative_broadcast" / "qml" / "Main.qml")))
if not engine.rootObjects():
    sys.exit(1)
win = engine.rootObjects()[0]


def shoot():
    win.grabWindow().save(sys.argv[1])
    print("gespeichert", sys.argv[1])
    app.quit()


QTimer.singleShot(2500, shoot)
sys.exit(app.exec())
