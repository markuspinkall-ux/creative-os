"""Fotos des Startmenüs in allen drei Stilen (Kategorien · A–Z · Kacheln) mit dem echten App-Modell.
   QT_QPA_PLATFORM=offscreen python3 tools/startmenue-stile.py <ordner>"""
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp")
OUT.mkdir(parents=True, exist_ok=True)
tmp = Path(tempfile.mkdtemp())
os.environ.update(HOME=str(tmp), XDG_CONFIG_HOME=str(tmp / "cfg"), XDG_DATA_HOME=str(tmp / "data"),
                  XDG_DATA_DIRS=str(tmp / "sys"))
apps_dir = tmp / "sys/applications"
apps_dir.mkdir(parents=True)
for f in ROOT.rglob("*.desktop"):
    if ".git" in f.parts or "Categories=" not in f.read_text(encoding="utf-8", errors="ignore"):
        continue
    text = f.read_text(encoding="utf-8")
    text = "\n".join(l for l in text.splitlines() if not l.startswith(("TryExec", "OnlyShowIn", "NotShowIn", "NoDisplay")))
    (apps_dir / f.name).write_text(text + "\n", encoding="utf-8")
for name, cat in (("Steam", "Game;"), ("Discord", "Network;InstantMessaging;"), ("GIMP", "Graphics;"),
                  ("LibreOffice Calc", "Office;Spreadsheet;"), ("VS Code", "Development;IDE;")):
    (apps_dir / f"{name.lower().replace(' ', '-')}.desktop").write_text(
        f"[Desktop Entry]\nType=Application\nName={name}\nExec=true\nCategories={cat}\n", encoding="utf-8")
sys.path.insert(0, str(ROOT / "shell"))

from PySide6.QtCore import QObject, QTimer, QUrl, Slot  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtQml import QQmlPropertyMap  # noqa: E402
from PySide6.QtQuick import QQuickView  # noqa: E402
from PySide6.QtQuickControls2 import QQuickStyle  # noqa: E402

QQuickStyle.setStyle("Basic")
app = QGuiApplication(sys.argv)
from creative_shell import config  # noqa: E402
from creative_shell.apps import AppModel  # noqa: E402


class Icons(QObject):
    @Slot(str, result=str)
    def app(self, name):
        return self.url(name.replace("creative-", "").replace("gibeon-", ""))

    @Slot(str, result=str)
    def url(self, name):
        p = ROOT / "shell/creative_shell/qml/Creative/icons" / f"{name}.svg"
        return QUrl.fromLocalFile(str(p)).toString() if p.exists() else ""


class Dummy(QObject):
    @Slot()
    def closePopups(self): pass

    @Slot(str)
    def addApp(self, d): pass

    @Slot()
    def refreshServer(self): pass

    @Slot()
    def refreshAvatar(self): pass

    @Slot()
    def lock(self): pass


apps = AppModel([])
view = QQuickView()
view.engine().addImportPath(str(ROOT / "shell/creative_shell/qml"))
session = QQmlPropertyMap()
for k, v in {"userName": "Markus", "initials": "M", "avatar": "", "serverMode": False, "serverModeAvailable": False}.items():
    session.insert(k, v)
icons, dummy = Icons(), Dummy()
ctx = view.rootContext()
for name, obj in {"apps": apps, "iconFiles": icons, "shell": dummy, "shelf": dummy}.items():
    ctx.setContextProperty(name, obj)
ctx.setContextProperty("session", session)
menu_url = QUrl.fromLocalFile(str(ROOT / "shell/creative_shell/qml/surfaces/StartMenu.qml")).toString()
Path(tmp / "test.qml").write_text(f'''
import QtQuick
import Creative
Rectangle {{ width: 460; height: 720; color: Theme.ground
    Loader {{ anchors.fill: parent; source: "{menu_url}" }} }}
''')
view.setSource(QUrl.fromLocalFile(str(tmp / "test.qml")))
errs = [e.toString() for e in view.errors()]
if errs:
    print("\n".join(errs))
    sys.exit(1)
view.resize(460, 720)
view.show()
steps = [("kategorien", ""), ("alphabet", ""), ("kacheln", ""), ("kacheln", "Kreativ und Medien")]
failed = []


def step():
    if not steps:
        app.exit(1 if failed else 0)
        return
    style, cat = steps.pop(0)
    config.set_value("startMenuStyle", style)
    apps.refreshStyle()
    apps.setCategory(cat)
    if apps.property("style") != style:
        failed.append(style)

    def shoot():
        name = f"startmenue-{style}{'-' + cat.split()[0].lower() if cat else ''}.png"
        view.grabWindow().save(str(OUT / name))
        print("Foto:", name, "Kategorien:", apps.property("categories"))
        step()
    QTimer.singleShot(700, shoot)


QTimer.singleShot(500, step)
sys.exit(app.exec())
