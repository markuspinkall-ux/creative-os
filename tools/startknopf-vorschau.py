"""Startknopf-Animation als Bildstreifen: python3 tools/startknopf-vorschau.py bild.png
(QT_QPA_PLATFORM=offscreen). Zeigt den Knopf vor dem Klick und zu mehreren Zeitpunkten danach."""
import sys
from pathlib import Path

from PySide6.QtCore import QMetaObject, QTimer, QUrl
from PySide6.QtGui import QGuiApplication, QImage, QPainter, QColor
from PySide6.QtQuick import QQuickView

ROOT = Path(__file__).resolve().parent.parent
out = sys.argv[1]
app = QGuiApplication(sys.argv)
view = QQuickView()
view.engine().addImportPath(str(ROOT / "shell/creative_shell/qml"))
Path("/tmp/startknopf.qml").write_text("""
import QtQuick
import Creative
Rectangle {
    width: 80; height: 80; color: "#1c2029"
    function go() { b.fly() }
    StartButton { id: b; anchors.centerIn: parent }
}
""")
view.setSource(QUrl.fromLocalFile("/tmp/startknopf.qml"))
for e in view.errors():
    print(e.toString())
view.show()
times = [0, 60, 140, 220, 290, 360, 450, 620]
frames = []


def grab(i):
    frames.append(view.grabWindow())
    if i + 1 < len(times):
        QTimer.singleShot(times[i + 1] - times[i], lambda: grab(i + 1))
    else:
        scale = 3
        strip = QImage(80 * scale * len(frames), 80 * scale, QImage.Format_RGB32)
        strip.fill(QColor("#1c2029"))
        p = QPainter(strip)
        for k, f in enumerate(frames):
            p.drawImage(k * 80 * scale, 0, f.scaled(80 * scale, 80 * scale))
        p.end()
        strip.save(out)
        print("gespeichert:", out)
        app.quit()


def start():
    QMetaObject.invokeMethod(view.rootObject(), "go")
    grab(0)


QTimer.singleShot(1500, start)
sys.exit(app.exec())
