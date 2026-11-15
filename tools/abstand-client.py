"""Testfenster für Creative Abstand (läuft unter kwin_wayland --virtual).
Maximiert sich, meldet Größe und Zustand, maximiert dann nochmal (= wiederherstellen)."""
import json
import sys

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QRasterWindow

app = QGuiApplication(sys.argv)
out = []


class Win(QRasterWindow):
    def paintEvent(self, _e):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#1c2029"))
        p.setPen(QColor("#dce6ff"))
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Creative Abstand")


w = Win()
w.setTitle("Abstand-Test")
w.resize(700, 450)
w.show()


def note(step):
    s = w.screen().availableGeometry()
    out.append({"step": step, "w": w.width(), "h": w.height(), "x": w.x(), "y": w.y(),
                "maximized": bool(w.windowStates() & Qt.WindowState.WindowMaximized),
                "screen": [s.width(), s.height()]})
    print(json.dumps(out[-1]), flush=True)


QTimer.singleShot(2000, lambda: note("normal"))
QTimer.singleShot(2500, w.showMaximized)
QTimer.singleShot(5000, lambda: note("maximiert"))
QTimer.singleShot(5500, w.showMaximized)       # nochmal maximieren = alte Größe
QTimer.singleShot(8000, lambda: note("wieder normal"))
QTimer.singleShot(8500, app.quit)
app.exec()
json.dump(out, open(sys.argv[1] if len(sys.argv) > 1 else "/tmp/abstand.json", "w"))
