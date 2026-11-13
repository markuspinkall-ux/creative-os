"""Creative 3D fotografieren (ohne Grafikkarte): Einrichtungsseite für TRELLIS.2.
   QT_QPA_PLATFORM=offscreen python3 tools/c3d-vorschau.py <ausgabe.png> [trellis|trellis2]"""
import importlib.machinery
import importlib.util
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ.setdefault("CREATIVE3D_HOME", tempfile.mkdtemp())
os.environ["CREATIVE3D_NO_WEB"] = "1"
sys.argv = ["creative-3d"]
loader = importlib.machinery.SourceFileLoader("c3d", str(ROOT / "creative3d/creative-3d"))
spec = importlib.util.spec_from_loader("c3d", loader)
c3d = importlib.util.module_from_spec(spec)
loader.exec_module(c3d)

from PySide6.QtCore import QSettings, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

out = sys.argv_out = None
app = QApplication.instance() or QApplication([])
QSettings("Creative OS", "Creative 3D").setValue("modell", os.environ.get("C3D_MODELL", "trellis2"))
win = c3d.Creative3D(preview_web=False)
win.resize(1240, 820)
win.show()


def shot():
    win.grab().save(os.environ["C3D_FOTO"])
    print("Foto:", os.environ["C3D_FOTO"])
    app.quit()


QTimer.singleShot(1200, shot)
app.exec()
