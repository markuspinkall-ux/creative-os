"""Startmenü › Rechtsklick: angeheftete Apps nur in der Taskleiste lösen, Entfernen mit Nachfrage.
   QT_QPA_PLATFORM=offscreen python3 tools/startmenue-vorschau.py <ordner>"""
import sys
from pathlib import Path

from PySide6.QtCore import QAbstractListModel, QByteArray, QModelIndex, QObject, QPoint, QPointF, Qt, QTimer, QUrl, Property, Signal, Slot
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlPropertyMap
from PySide6.QtQuick import QQuickItem, QQuickView
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtTest import QTest

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp")
OUT.mkdir(parents=True, exist_ok=True)
QQuickStyle.setStyle("Basic")
app = QGuiApplication(sys.argv)

ROWS = [("Dateien", "creative-files.desktop", "files", True), ("Mail", "creative-mail.desktop", "mail", False),
        ("Notes", "creative-notes.desktop", "notes", False), ("Pictures", "creative-pictures.desktop", "pictures", False),
        ("Steam", "steam.desktop", "games", True), ("Taschenrechner", "creative-calculator.desktop", "calculator", False)]
calls = []


class Apps(QAbstractListModel):
    folderChanged = Signal()

    def rowCount(self, parent=QModelIndex()):
        return len(ROWS)

    def roleNames(self):
        return {i + 256: QByteArray(n.encode()) for i, n in enumerate(
            ["name", "icon", "desktopId", "letter", "comment", "isFolder", "folderIcons", "folderCount"])}

    def data(self, index, role):
        n, d, ic, _p = ROWS[index.row()]
        return {256: n, 257: ic, 258: d, 259: n[0], 260: "", 261: False, 262: [], 263: 0}.get(role)

    folder = Property(str, lambda self: "", notify=folderChanged)
    folderName = Property(str, lambda self: "", notify=folderChanged)
    filterText = Property(str, lambda self: "", lambda self, v: None, notify=folderChanged)

    @Slot()
    def closeFolder(self): pass

    @Slot(int, result=bool)
    def launchAt(self, i): return False

    @Slot(str, result=bool)
    def isPinned(self, d): return any(r[1] == d and r[3] for r in ROWS)

    @Slot(str)
    def pin(self, d): calls.append(("pin", d))

    @Slot(str)
    def unpin(self, d): calls.append(("unpin", d))

    @Slot(str)
    def hideFromStartMenu(self, d): calls.append(("hide", d))


class Icons(QObject):
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


view = QQuickView()
view.engine().addImportPath(str(ROOT / "shell/creative_shell/qml"))
apps, icons, dummy = Apps(), Icons(), Dummy()
session = QQmlPropertyMap()
for k, v in {"userName": "Markus", "initials": "M", "avatar": "", "serverMode": False, "serverModeAvailable": False}.items():
    session.insert(k, v)
ctx = view.rootContext()
for name, obj in {"apps": apps, "iconFiles": icons, "shell": dummy, "shelf": dummy}.items():
    ctx.setContextProperty(name, obj)
ctx.setContextProperty("session", session)
menu_url = QUrl.fromLocalFile(str(ROOT / "shell/creative_shell/qml/surfaces/StartMenu.qml")).toString()
Path("/tmp/startmenue-test.qml").write_text(f'''
import QtQuick
import Creative
Rectangle {{
    width: 460; height: 640; color: Theme.ground
    Loader {{ anchors.fill: parent; source: "{menu_url}" }}
}}
''')
view.setSource(QUrl.fromLocalFile("/tmp/startmenue-test.qml"))
errors = [e.toString() for e in view.errors()]
view.resize(460, 640)
view.show()
ok = []


def find(name):
    return view.rootObject().findChild(QQuickItem, name)


def click_item(item):
    p = item.mapToScene(QPointF(item.width() / 2, item.height() / 2))
    QTest.mouseClick(view, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(int(p.x()), int(p.y())))


def row_point(text):
    for it in view.rootObject().findChildren(QQuickItem):
        if it.property("text") == text and it.isVisible():
            p = it.mapToScene(QPointF(it.width() / 2, it.height() / 2))
            return QPoint(int(p.x()), int(p.y()))
    raise SystemExit(f"Zeile {text} nicht gefunden")


def shot(name):
    view.grabWindow().save(str(OUT / name))
    print("Foto:", OUT / name)


def step():
    try:
        # 1) angeheftete App: kein „lösen“ im Startmenü
        QTest.mouseClick(view, Qt.MouseButton.RightButton, Qt.KeyboardModifier.NoModifier, row_point("Steam"))
        QTest.qWait(300)
        pin = find("pinRow")
        assert pin and pin.isVisible() and pin.property("active") is False, "angeheftete App lässt sich im Startmenü lösen"
        assert pin.property("label") == "In der Taskleiste angeheftet", pin.property("label")
        click_item(pin)
        QTest.qWait(100)
        assert not any(c[0] == "unpin" for c in calls), calls
        ok.append("angeheftete App nur in der Taskleiste lösbar")
        shot("startmenue-angeheftet.png")
        # 2) nicht angeheftet: anheften geht
        QTest.mouseClick(view, Qt.MouseButton.RightButton, Qt.KeyboardModifier.NoModifier, row_point("Notes"))
        QTest.qWait(300)
        assert find("pinRow").property("active") is True
        # 3) Entfernen fragt nach
        click_item(find("hideRow"))
        QTest.qWait(300)
        assert not calls, f"ohne Nachfrage entfernt: {calls}"
        assert find("hideConfirm").isVisible(), "keine Nachfrage"
        shot("startmenue-nachfrage.png")
        click_item(find("hideCancel"))
        QTest.qWait(200)
        assert not calls, calls
        ok.append("Abbrechen entfernt nichts")
        click_item(find("hideRow"))
        QTest.qWait(300)
        click_item(find("hideConfirm"))
        QTest.qWait(200)
        assert calls == [("hide", "creative-notes.desktop")], calls
        ok.append("Entfernen nach Bestätigung")
        print("\n".join("✓ " + o for o in ok))
        print("Startmenü-Rechtsklick: alles in Ordnung")
        app.exit(0)
    except BaseException as e:  # noqa: BLE001
        print("FEHLER:", e)
        shot("startmenue-fehler.png")
        app.exit(1)


if errors:
    print("\n".join(errors))
QTimer.singleShot(1500, step)
sys.exit(app.exec())
