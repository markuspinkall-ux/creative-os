"""Startet Szene (Layer-Shell) oder Fenster: zeigen.py szene|fenster"""
import sys
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QGuiApplication, QWindow
from PySide6.QtQml import QQmlApplicationEngine

here = Path(__file__).resolve().parent
root = here.parent.parent
app = QGuiApplication(sys.argv)
app.setDesktopFileName("creative-files")
engine = QQmlApplicationEngine()
if sys.argv[1] == "szene":
    engine.setInitialProperties({
        "wallpaper": QUrl.fromLocalFile(str(root / "image/netinstall/installer/pixmaps/creative-wallpaper.png")),
        "iconDir": QUrl.fromLocalFile(str(root / "shell/creative_shell/qml/Creative/icons")),
    })
    engine.load(here / "szene.qml")
else:
    engine.load(here / "fenster.qml")
    win = engine.rootObjects()[0]
    QTimer.singleShot(1500, win.showMaximized)
if not engine.rootObjects():
    sys.exit(1)
app.exec()
