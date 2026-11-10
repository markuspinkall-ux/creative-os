#!/usr/bin/python3
"""Erzeugt beim Bauen die Graphit-Bausteine (Datei-/Bildauswahl, Rückfrage,
Avatar, Knöpfe) einmal wirklich – nicht nur übersetzen. Fehlt eine Eigenschaft
oder ist eine Bindung kaputt, bricht der Build ab.

  python3 qml-bausteine.py
"""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QUrl                           # noqa: E402
from PySide6.QtGui import QGuiApplication                 # noqa: E402
from PySide6.QtQml import QQmlComponent, QQmlEngine       # noqa: E402
from PySide6.QtQuickControls2 import QQuickStyle          # noqa: E402

SHELL_QML = "/usr/lib/creative-shell/creative_shell/qml"
BAUSTEINE = b"""
import QtQuick
import QtQuick.Controls.Basic
import Creative
ApplicationWindow {
    FilePicker { mode: "open" }
    FilePicker { mode: "save" }
    FilePicker { mode: "folder" }
    ImagePicker {}
    ConfirmDialog { danger: true }
    Avatar {}
    CButton { danger: true }
}
"""


def main():
    QQuickStyle.setStyle("Basic")
    app = QGuiApplication(sys.argv[:1])
    engine = QQmlEngine()
    engine.addImportPath(SHELL_QML)
    failed = False

    def check(component, name):
        nonlocal failed
        if component.status() == QQmlComponent.Status.Error:
            failed = True
            print(f"QML-FEHLER in {name}:")
            for error in component.errors():
                print("   ", error.toString())
        else:
            print(f"QML in Ordnung: {name}")

    # Bausteine wirklich erzeugen (prüft auch Eigenschaften und Bindungen)
    comp = QQmlComponent(engine)
    comp.setData(BAUSTEINE, QUrl("file:///bausteine.qml"))
    check(comp, "Creative-Bausteine")
    if comp.status() == QQmlComponent.Status.Ready:
        obj = comp.create()
        if obj is None:
            failed = True
            print("QML-FEHLER: Bausteine ließen sich nicht erzeugen:")
            for error in comp.errors():
                print("   ", error.toString())
    del app
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
