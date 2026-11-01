#!/usr/bin/python3
"""Prüft beim Bauen, ob sich die QML-Oberflächen übersetzen lassen.

Aufruf: qml-check.py <qml-Datei> …   (Fehler werden ausgegeben; Ausgang 1 bei Fehlern)
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QUrl  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtQml import QQmlComponent, QQmlEngine  # noqa: E402
from PySide6.QtQuickControls2 import QQuickStyle  # noqa: E402

QQuickStyle.setStyle("Basic")
app = QGuiApplication(sys.argv[:1])
engine = QQmlEngine()
engine.addImportPath("/usr/lib/creative-shell/creative_shell/qml")
bad = 0
for path in sys.argv[1:]:
    comp = QQmlComponent(engine, QUrl.fromLocalFile(os.path.abspath(path)))
    if comp.isError():
        bad += 1
        for err in comp.errors():
            print(f"QML-FEHLER {err.toString()}")
    else:
        print(f"QML ok: {path}")
sys.exit(1 if bad else 0)
