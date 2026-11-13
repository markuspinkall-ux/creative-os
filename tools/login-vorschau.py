"""Vorschau des Anmeldebildschirms (SDDM-Theme) ohne SDDM: Fotos normal / Server-Modus.

  python3 tools/login-vorschau.py <ausgabe.png>
Liest wie das echte Theme /var/lib/creative-os/login-look.json und
/var/lib/creative-servermode/state.json (QML_XHR_ALLOW_FILE_READ=1 nötig).
"""

import sys
from pathlib import Path

from PySide6.QtCore import Property, QObject, QTimer, QUrl, Signal, Slot, Qt
from PySide6.QtGui import QGuiApplication, QStandardItem, QStandardItemModel
from PySide6.QtQuick import QQuickView

ROOT = Path(__file__).resolve().parent.parent


class Users(QStandardItemModel):
    def __init__(self):
        super().__init__()
        for name, real in (("markus", "Markus"), ("kathrin", "Kathrin")):
            it = QStandardItem(real)
            it.setData(name, Qt.UserRole + 1)
            it.setData(real, Qt.UserRole + 2)
            it.setData("", Qt.UserRole + 4)
            self.appendRow(it)

    count = Property(int, lambda self: self.rowCount(), constant=True)
    lastIndex = Property(int, lambda self: 0, constant=True)


class Sessions(QStandardItemModel):
    def __init__(self):
        super().__init__()
        it = QStandardItem("Creative OS")
        it.setData("creative.desktop", Qt.UserRole + 2)
        it.setData("Creative OS", Qt.UserRole + 4)
        self.appendRow(it)

    lastIndex = Property(int, lambda self: 0, constant=True)


class Sddm(QObject):
    loginFailed = Signal()
    loginSucceeded = Signal()
    canReboot = Property(bool, lambda self: True, constant=True)
    canPowerOff = Property(bool, lambda self: True, constant=True)

    @Slot(str, str, int)
    def login(self, *_):
        pass

    @Slot()
    def reboot(self):
        pass

    @Slot()
    def powerOff(self):
        pass


class Keyboard(QObject):
    capsLock = Property(bool, lambda self: False, constant=True)


def main():
    out = sys.argv[1]
    app = QGuiApplication(sys.argv[:1])
    view = QQuickView()
    ctx = view.rootContext()
    keep = [Users(), Sessions(), Sddm(), Keyboard()]
    ctx.setContextProperty("userModel", keep[0])
    ctx.setContextProperty("sessionModel", keep[1])
    ctx.setContextProperty("sddm", keep[2])
    ctx.setContextProperty("keyboard", keep[3])
    ctx.setContextProperty("config", {"background": "background.svg"})
    view.setResizeMode(QQuickView.SizeRootObjectToView)
    view.resize(1600, 900)
    view.setSource(QUrl.fromLocalFile(str(ROOT / "login/creative/Main.qml")))
    for e in view.errors():
        print("QML:", e.toString())
    if view.status() != QQuickView.Ready:
        return 1
    view.show()

    def shot():
        view.grabWindow().save(out)
        print("Foto:", out)
        app.quit()

    QTimer.singleShot(4500, shot)
    app.exec()
    return 0


if __name__ == "__main__":
    sys.exit(main())
