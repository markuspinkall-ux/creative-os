"""Bildschirmfoto einer Creative-App ohne Bildschirm (für die Entwicklung).
Aufruf: python3 tools/shot.py <modul> <ausgabe.png> [wartezeit_ms]"""
import importlib
import sys

mod, out = sys.argv[1], sys.argv[2]
wait = int(sys.argv[3]) if len(sys.argv) > 3 else 3000
sys.argv = [mod] + sys.argv[4:]
from PySide6.QtCore import QTimer
from PySide6.QtGui import QGuiApplication

_orig = QGuiApplication.exec


def _exec(self):
    def grab():
        for w in QGuiApplication.topLevelWindows():
            if w.isVisible() and hasattr(w, "grabWindow"):
                w.grabWindow().save(out)
                print("Foto:", out, w.width(), w.height())
                break
        QGuiApplication.quit()
    QTimer.singleShot(wait, grab)
    return _orig()


QGuiApplication.exec = _exec
m = importlib.import_module(mod + ".__main__")
sys.exit(m.main())
