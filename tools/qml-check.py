"""Prüft, ob alle QML-Dateien von Creative OS fehlerfrei geladen werden können
(Syntax, Importe, Komponenten) – ohne das Abbild zu bauen.

    QT_QPA_PLATFORM=offscreen python3 tools/qml-check.py
"""
import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtQuickControls2 import QQuickStyle

ROOT = Path(__file__).resolve().parent.parent
DIRS = ["shell/creative_shell/qml/Creative", "shell/creative_shell/qml/surfaces", "shell/creative_shell/qml",
        "files/creative_files/qml", "settings/creative_settings/qml", "settings/creative_settings/qml/pages"]

QQuickStyle.setStyle("Basic")
app = QGuiApplication(sys.argv)
engine = QQmlEngine()
engine.addImportPath(str(ROOT / "shell/creative_shell/qml"))
bad = 0
checked = 0
for d in DIRS:
    for f in sorted((ROOT / d).glob("*.qml")):
        if f.name.startswith("Host"):    # brauchen org.kde.layershell
            continue
        comp = QQmlComponent(engine, QUrl.fromLocalFile(str(f)))
        checked += 1
        if comp.isError():
            bad += 1
            for e in comp.errors():
                print(f"FEHLER {f.relative_to(ROOT)}: {e.toString()}")
# Eigene Datei mit dem Namen eines Creative-Bauteils wird von „import Creative“ überdeckt
# (so war „Papierkorb leeren“ in Dateien tot)
module = {l.split()[0] for l in (ROOT / "shell/creative_shell/qml/Creative/qmldir").read_text().splitlines()
          if l and l[0].isupper()}
for d in DIRS:
    if d.endswith("/Creative"):
        continue
    for f in sorted((ROOT / d).glob("*.qml")):
        if f.stem in module:
            bad += 1
            print(f"FEHLER {f.relative_to(ROOT)}: heißt wie das Creative-Bauteil {f.stem} und wird davon überdeckt")
print(f"{checked} QML-Dateien geprüft, {bad} mit Fehlern")
sys.exit(1 if bad else 0)
