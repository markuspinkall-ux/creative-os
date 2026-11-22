"""Testfenster für maximierte Fenster (läuft unter kwin_wayland --virtual).
Maximiert sich, meldet Größe und Zustand und stellt dann die alte Größe wieder her."""
import json
import sys

from PySide6.QtCore import QRect, QTimer, Qt
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QRasterWindow

app = QGuiApplication(sys.argv)
app.setDesktopFileName("creative-browser")   # wie der Browser – creative-tasks platziert ihn
out = []


class Win(QRasterWindow):
    def paintEvent(self, _e):
        p = QPainter(self)
        r = QRect(0, 0, self.width(), self.height())
        p.fillRect(r, QColor("#1c2029"))
        p.setPen(QColor("#dce6ff"))
        p.drawText(r, Qt.AlignmentFlag.AlignCenter, "Abstand")


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
QTimer.singleShot(5500, lambda: w.showNormal() if w.windowStates() & Qt.WindowState.WindowMaximized
                  else w.showMaximized())   # wiederherstellen
QTimer.singleShot(8000, lambda: note("wieder normal"))
QTimer.singleShot(8500, app.quit)
app.exec()
json.dump(out, open(sys.argv[1] if len(sys.argv) > 1 else "/tmp/abstand.json", "w"))
