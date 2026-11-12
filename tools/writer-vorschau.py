"""Bildschirmfotos von Creative Writer (Menüband-Reiter, Datei-Bereich) – für die Vorschau-Workflows.

    QT_QPA_PLATFORM=offscreen python3 tools/writer-vorschau.py ausgabe/ [präfix]
"""
import importlib.machinery
import importlib.util
import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

root = Path(__file__).resolve().parent.parent / "writer"
sys.path.insert(0, str(root))
loader = importlib.machinery.SourceFileLoader("creative_writer", str(root / "creative-writer"))
spec = importlib.util.spec_from_loader("creative_writer", loader)
cw = importlib.util.module_from_spec(spec)
sys.modules["creative_writer"] = cw
loader.exec_module(cw)

out = Path(sys.argv[1])
prefix = sys.argv[2] if len(sys.argv) > 2 else ""
out.mkdir(parents=True, exist_ok=True)
app = QApplication(sys.argv[:1])
app.setStyle("Fusion")
w = cw.Writer()
w.resize(1440, 900)
cw.demo(w)
w.show()
steps = [("start", lambda: w.ribbon.show_tab(0)), ("einfuegen", lambda: w.ribbon.show_tab(1)),
         ("layout", lambda: w.ribbon.show_tab(2)), ("ansicht", lambda: (w.ribbon.show_tab(4), w.set_zoom(80))),
         ("datei", lambda: w.show_backstage("export")), ("neu", lambda: w.show_backstage("new"))]


def run(i=0):
    if i:
        w.grab().save(str(out / f"{prefix}writer-{steps[i - 1][0]}.png"))
    if i == len(steps):
        app.quit()
        return
    steps[i][1]()
    QTimer.singleShot(500, lambda: run(i + 1))


QTimer.singleShot(1200, run)
app.exec()
print("Fotos:", sorted(p.name for p in out.iterdir()))
