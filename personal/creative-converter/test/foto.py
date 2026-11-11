"""Bildschirmfoto-Test für Creative Converter (läuft in GitHub Actions unter xvfb)."""
import importlib.machinery, importlib.util, sys
from pathlib import Path
from PySide6.QtCore import QPoint, QTimer
from PySide6.QtWidgets import QApplication

here = Path(__file__).resolve().parent.parent
loader = importlib.machinery.SourceFileLoader("cc", str(here / "creative-converter"))
spec = importlib.util.spec_from_loader("cc", loader)
cc = importlib.util.module_from_spec(spec)
sys.modules["cc"] = cc
loader.exec_module(cc)

app = QApplication(sys.argv)
w = cc.Converter()
w.move(0, 0)
w.show()
w.url.setText("https://www.youtube.com/watch?v=1GxnGLRvQdU")
w.add_entries([{"url": "https://youtu.be/a", "title": "Beispiel-Titel – Musikvideo", "uploader": "Kanal",
                "duration": 215, "thumb": ""}], None, "")
out = Path(sys.argv[1])

def shot(name):
    app.primaryScreen().grabWindow(0).save(str(out / name))

def step1():
    shot("1-fenster.png")
    menu = w.url.createStandardContextMenu()
    menu.popup(w.url.mapToGlobal(QPoint(320, 30)))
    QTimer.singleShot(600, lambda: (shot("2-kontextmenue.png"), menu.close(), step2()))

def step2():
    w.quality.showPopup()
    QTimer.singleShot(600, lambda: (shot("3-qualitaet.png"), app.quit()))

QTimer.singleShot(1200, step1)
app.exec()
