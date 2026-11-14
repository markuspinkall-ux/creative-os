"""Vorschau des Schnellzugriffs (QuickPanel) mit Beispieldaten.
   QT_QPA_PLATFORM=offscreen python3 tools/schnellzugriff-vorschau.py bild.png [an|aus]"""
import sys
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlPropertyMap
from PySide6.QtQuick import QQuickView
from PySide6.QtQuickControls2 import QQuickStyle

ROOT = Path(__file__).resolve().parent.parent
out = sys.argv[1]
awake = len(sys.argv) > 2 and sys.argv[2] == "an"

QQuickStyle.setStyle("Basic")
app = QGuiApplication(sys.argv)
view = QQuickView()
view.engine().addImportPath(str(ROOT / "shell/creative_shell/qml"))
keep = []


def ctx(name, **values):
    m = QQmlPropertyMap(view)
    for k, v in values.items():
        m.insert(k, v)
    keep.append(m)
    view.rootContext().setContextProperty(name, m)


ctx("audioOutput", available=True, muted=False, value=40)
ctx("network", available=True, busy=False, connected=True, message="", ssid="Zuhause",
    wifiEnabled=True, wired=False,
    networks=[{"ssid": "Zuhause", "strength": 80, "secured": True, "inUse": True, "known": True}])
ctx("brightness", displays=[{"name": "Hauptbildschirm", "key": "1", "value": 70}])
ctx("printers", attention=False, available=False, name="", statusText="Kein Drucker eingerichtet")
ctx("session", keepAwake=awake, keepAwakeAvailable=True)
ctx("shell", panelFocus="")
view.setResizeMode(QQuickView.SizeRootObjectToView)
view.setSource(QUrl.fromLocalFile(str(ROOT / "shell/creative_shell/qml/surfaces/QuickPanel.qml")))
for e in view.errors():
    print(e.toString())
view.resize(420, 1250)
view.show()


def shoot():
    view.grabWindow().save(out)
    print("gespeichert:", out)
    app.quit()


QTimer.singleShot(2500, shoot)
sys.exit(app.exec())
