"""Schreibtisch (Wallpaper.qml) ohne Bildschirm rendern – mit echten Modellen, Shell nur nachgebildet."""
import json, os, sys
from pathlib import Path
out = sys.argv[1]
home = Path(os.environ["HOME"])
cfg = home / ".config/creative-os"; cfg.mkdir(parents=True, exist_ok=True)
(cfg / "shell.json").write_text(json.dumps({"shelf": [str(home / "Schreibtisch/Projekte"), str(home / "Schreibtisch/notiz.txt")]}))
from PySide6.QtCore import Property, QObject, QTimer, QUrl, Slot, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtQuick import QQuickView
from PySide6.QtQuickControls2 import QQuickStyle
QQuickStyle.setStyle("Basic")
app = QGuiApplication(sys.argv)
from creative_shell.mainthread import install as _mt_install
_mt_timer = _mt_install()
from creative_shell.apps import AppModel
from creative_shell.desktop import DesktopModel
from creative_shell.desktopstats import DesktopStats
from creative_shell.shelf import ShelfModel
from creative_shell.icons import IconProvider
from creative_shell import config


class FakeShell(QObject):
    @Slot()
    def closePopups(self): pass
    primaryScreen = Property(str, lambda self: "", constant=True)


class Fake(QObject):
    changed = Signal()
    @Slot()
    def showDesktop(self): pass
    @Slot()
    def openSettings(self): pass
    @Slot(bool)
    def setEnabled(self, v): pass
    enabled = Property(bool, lambda self: False, constant=True)


view = QQuickView()
view.engine().addImportPath(str(Path("shell/creative_shell/qml").resolve()))
view.engine().addImageProvider("icon", IconProvider())
apps = AppModel(config.load()["pinned"])
ctx = view.rootContext()
for k, v in {"shell": FakeShell(), "desktop": DesktopModel(), "desktopStats": DesktopStats(), "shelf": ShelfModel(apps),
             "tasks": Fake(), "session": Fake(), "visualizer": Fake()}.items():
    ctx.setContextProperty(k, v)
    globals()["_keep_" + k] = v
ctx.setContextProperty("wallpaperUrl", QUrl.fromLocalFile(str(Path("shell/creative_shell/qml/Creative/wallpapers/graphit.svg").resolve())))
view.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
view.resize(1600, 900)
view.setSource(QUrl.fromLocalFile(str(Path("shell/creative_shell/qml/surfaces/Wallpaper.qml").resolve())))
for e in view.errors():
    print("QML-FEHLER:", e.toString())
view.show()
def grab():
    view.grabWindow().save(out); print("Foto:", out); app.quit()
QTimer.singleShot(5000, grab)
app.exec()
