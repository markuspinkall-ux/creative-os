"""Vorschau: Programmname über einem Taskleisten-Symbol (TaskTip.qml über einer nachgebauten Leiste).
   QT_QPA_PLATFORM=offscreen python3 tools/tasktip-vorschau.py bild.png"""
import sys
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlPropertyMap
from PySide6.QtQuick import QQuickView
from PySide6.QtQuickControls2 import QQuickStyle

ROOT = Path(__file__).resolve().parent.parent
QQuickStyle.setStyle("Basic")
app = QGuiApplication(sys.argv)
view = QQuickView()
view.engine().addImportPath(str(ROOT / "shell/creative_shell/qml"))
shell = QQmlPropertyMap()
shell.insert("taskTip", {"screen": "DP-1", "text": "Creative Browser", "x": 196.0, "count": 2})
view.rootContext().setContextProperty("shell", shell)
tip = QUrl.fromLocalFile(str(ROOT / "shell/creative_shell/qml/surfaces/TaskTip.qml")).toString()
qml = f'''
import QtQuick
import Creative
Rectangle {{
    width: 520; height: 124
    color: "#2a3140"
    Loader {{ x: 0; y: 0; width: parent.width; height: 64; source: "{tip}"; onLoaded: item.screenName = "DP-1" }}
    Rectangle {{
        y: 64; width: parent.width; height: 60; color: Theme.surface
        Row {{
            x: 14; anchors.verticalCenter: parent.verticalCenter; spacing: 8
            Repeater {{
                model: ["grid", "folder", "browser", "terminal", "music"]
                delegate: Rectangle {{
                    required property string modelData
                    required property int index
                    width: 44; height: 44; radius: Theme.radiusButton
                    color: index === 2 ? Theme.hover : "transparent"
                    SvgIcon {{ anchors.centerIn: parent; name: modelData; size: 22 }}
                }}
            }}
        }}
    }}
}}
'''
Path("/tmp/tasktip-test.qml").write_text(qml)
view.setSource(QUrl.fromLocalFile("/tmp/tasktip-test.qml"))
for e in view.errors():
    print(e.toString())
view.show()
QTimer.singleShot(1200, lambda: (view.grabWindow().save(sys.argv[1]), print("Foto:", sys.argv[1]), app.quit()))
sys.exit(app.exec())
