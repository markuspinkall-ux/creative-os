"""Bildschirmfotos des Creative-Engine-Editors (Graphit und Porzellan) – für den Workflow „Creative Engine prüfen“.

    QT_QPA_PLATFORM=offscreen python3 tools/engine-editor-vorschau.py ausgabe/ [präfix]
"""
import os
import sys
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root / "engine"))
os.environ["HOME"] = tempfile.mkdtemp()          # eigene „zuletzt geöffnet“-Liste
os.environ.pop("XDG_CONFIG_HOME", None)
look = Path(sys.argv[3]) if len(sys.argv) > 3 else None
if look:
    (Path(os.environ["HOME"]) / ".config/creative-os").mkdir(parents=True)
    (Path(os.environ["HOME"]) / ".config/creative-os/look.conf").write_text(look.read_text())

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from creative_engine import app as engine, project as proj, skeleton as S  # noqa: E402

out = Path(sys.argv[1]).resolve()
prefix = sys.argv[2] if len(sys.argv) > 2 else ""
out.mkdir(parents=True, exist_ok=True)
qt = QApplication(sys.argv[:1])
from PySide6.QtCore import QLocale  # noqa: E402
QLocale.setDefault(QLocale(QLocale.Language.German, QLocale.Country.Germany))
qt.setStyle("Fusion")
engine.apply_palette(qt)
qt.setStyleSheet(engine.stylesheet())
w = engine.Window()
w.resize(1440, 900)
w.show()

folder = Path(os.environ["HOME"]) / "Creative Engine" / "Insel-Abenteuer"
data = proj.new_project("Insel-Abenteuer")
proj.add_step(data, "text", 1)
proj.save(folder, data)
(folder / "assets").mkdir(parents=True, exist_ok=True)
S.demo_glb(folder / "assets" / "held.glb")
S.demo_glb(folder / "assets" / "baum.glb")
level = data["levels"][next(s["id"] for s in data["flow"] if s["type"] == "level")]
level["decor"] += [{"model": "assets/baum.glb", "x": 14, "y": 2, "z": -4, "height": 4},
                   {"model": "assets/baum.glb", "x": 30, "y": 2, "z": -6, "height": 5}]
proj.save(folder, data)
dialogs = []


def character():
    from creative_engine.character import CharacterEditor
    dlg = CharacterEditor(w, w.folder, w.project)
    dlg.resize(1320, 820)
    dlg.show()
    dlg.desc.setPlainText("watschelt wie eine Ente und schlackert mit den Armen")
    dlg.guess_from_text()
    dlg.assign("walk")
    dlg.preview.t = 0.3
    dlg.preview.timer.stop()
    dialogs.append(dlg)


def shot(name, widget=None):
    (widget or w).grab().save(str(out / f"{prefix}engine-{name}.png"))


steps = [
    ("start", lambda: None, None),
    ("level", lambda: w.open_project(str(folder)), None),
    ("level-auswahl", lambda: (w.levels.set_tool("select"), w.levels.show_props(level["entities"][2])), None),
    ("menue", lambda: (w.timeline.setCurrentRow(1)), None),
    ("splash", lambda: w.timeline.setCurrentRow(0), None),
    ("einstellungen", lambda: w.show_section("settings"), None),
    ("charakter", character, lambda: dialogs[0]),
]


def run(i=0):
    if i:
        name, _act, target = steps[i - 1]
        shot(name, target() if target else None)
    if i == len(steps):
        for d in dialogs:
            d.preview.timer.stop()
        qt.quit()
        return
    steps[i][1]()
    QTimer.singleShot(600, lambda: run(i + 1))


QTimer.singleShot(800, run)
qt.exec()
print("Fotos:", sorted(p.name for p in out.iterdir()))
