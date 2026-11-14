"""Dateien › Papierkorb: Klick auf „Papierkorb leeren“, Rückfrage bestätigen, Papierkorb muss leer sein.
   QT_QPA_PLATFORM=offscreen python3 tools/papierkorb-test.py [fotoordner]"""
import os
import sys
import tempfile
from pathlib import Path

home = Path(tempfile.mkdtemp())
os.environ["HOME"] = str(home)
os.environ["XDG_DATA_HOME"] = str(home / ".local" / "share")
os.environ["XDG_CONFIG_HOME"] = str(home / ".config")
trash = home / ".local" / "share" / "Trash"
(trash / "files").mkdir(parents=True)
(trash / "info").mkdir(parents=True)
for i, name in enumerate(("Urlaub.jpg", "Notizen.txt")):
    (trash / "files" / name).write_text("x")
    (trash / "info" / f"{name}.trashinfo").write_text(
        f"[Trash Info]\nPath=/home/test/{name}\nDeletionDate=2026-11-1{i}T10:00:00\n")
(trash / "files" / "Waise.txt").write_text("ohne Info-Datei")      # zählt im Tray, fehlt in der Liste

fotos = Path(sys.argv[1]) if len(sys.argv) > 1 else None
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root / "files"))

from PySide6.QtCore import QPoint, QPointF, Qt, QTimer, QUrl  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402
from PySide6.QtQuick import QQuickItem  # noqa: E402
from PySide6.QtQuickControls2 import QQuickStyle  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402

QQuickStyle.setStyle("Basic")
app = QGuiApplication(sys.argv)
from creative_files.backend import FileManager  # noqa: E402

engine = QQmlApplicationEngine()
engine.addImportPath(str(root / "shell" / "creative_shell" / "qml"))
fm = FileManager(None)
fm.openPage("trash")
engine.rootContext().setContextProperty("fm", fm)
engine.load(QUrl.fromLocalFile(str(root / "files" / "creative_files" / "qml" / "Main.qml")))
assert engine.rootObjects(), "Main.qml lädt nicht"
win = engine.rootObjects()[0]
win.resize(1000, 640)
win.show()


def items(node):
    for child in node.childItems():
        yield child
        yield from items(child)


def find(text):
    for it in items(win.contentItem().parentItem() or win.contentItem()):
        try:
            if it.property("text") == text and it.isVisible() and it.width() > 0:
                return it
        except RuntimeError:
            pass
    return None


def click(text):
    it = find(text)
    assert it is not None, f"Knopf „{text}“ nicht gefunden"
    p = it.mapToScene(QPointF(it.width() / 2, it.height() / 2))
    print(f"Klick auf „{text}“ bei {int(p.x())},{int(p.y())}")
    QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, QPoint(int(p.x()), int(p.y())))


def shot(name):
    if fotos:
        fotos.mkdir(parents=True, exist_ok=True)
        win.grabWindow().save(str(fotos / name))


steps = []


def step(fn):
    steps.append(fn)


@step
def vorher():
    shot("1-papierkorb.png")
    click("Papierkorb leeren")


@step
def rueckfrage():
    shot("2-rueckfrage.png")
    click("Endgültig löschen")


@step
def nachher():
    shot("3-geleert.png")
    rest = sorted(p.name for p in (trash / "files").iterdir()) + sorted(p.name for p in (trash / "info").iterdir())
    if rest:
        print("FEHLER: Papierkorb nicht leer:", rest)
        app.exit(1)
    else:
        print("Papierkorb leeren: alles in Ordnung")
        app.exit(0)


def run_next():
    if steps:
        steps.pop(0)()
        QTimer.singleShot(800, run_next)


QTimer.singleShot(1500, run_next)
QTimer.singleShot(15000, lambda: (print("FEHLER: Zeitüberschreitung"), app.exit(2)))
sys.exit(app.exec())
