"""Vorschau der Rechtsklick-Menüs (CMenu, CTextMenu) in Graphit und Porzellan als Bild.

    QT_QPA_PLATFORM=offscreen python3 tools/menue-vorschau.py ausgabe.png
"""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
out = sys.argv[1] if len(sys.argv) > 1 else "menues.png"

QML = """
import QtQuick
import QtQuick.Templates as GibeonT
import QtQuick.Controls.Basic
import Creative
Rectangle {
    width: 760; height: 380
    color: Theme.ground
    Text { x: 24; y: 18; text: "Studio-Quelle (Kamera)"; color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 12 }
    Item { id: a; x: 24; y: 40 }
    CMenu {
        id: m
        CMenuItem { text: "Ausblenden" }
        CMenuItem { text: "Bildfüllend" }
        CMenuItem { text: "Nach vorne" }
        CMenuItem { text: "Nach hinten"; enabled: false }
        CMenuSeparator {}
        CMenuItem { text: "Löschen"; danger: true }
    }
    Text { x: 400; y: 18; text: "Textfeld"; color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: 12 }
    TextField {
        id: f; x: 400; y: 40; width: 300; text: "Hallo Gibeon OS"
        GibeonT.ContextMenu.menu: CTextMenu { id: tm }
    }
    Timer {
        interval: 300; running: true
        onTriggered: { m.popup(a, 0, 0); f.selectAll(); tm.popup(f, 40, 40); m.currentIndex = 1 }
    }
}
"""


def shot(design, path):
    cfg = tempfile.mkdtemp()
    (Path(cfg) / "creative-os").mkdir()
    (Path(cfg) / "creative-os" / "look.conf").write_text(f"[Look]\ndesign={design}\naccent=blau\n")
    os.environ["XDG_CONFIG_HOME"] = cfg
    import subprocess
    code = f"""
import sys
sys.path.insert(0, {str(ROOT / 'shell')!r})
from PySide6.QtCore import QUrl, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtQuick import QQuickView
from PySide6.QtQuickControls2 import QQuickStyle
QQuickStyle.setStyle("Basic")
app = QGuiApplication(sys.argv)
try:
    from creative_shell.look import LookModel
except Exception:
    LookModel = None
v = QQuickView()
v.engine().addImportPath({str(ROOT / 'shell/creative_shell/qml')!r})
if LookModel:
    lm = LookModel()
    v.rootContext().setContextProperty("look", lm)
open('/tmp/menue.qml', 'w').write({QML!r})
v.setSource(QUrl.fromLocalFile('/tmp/menue.qml'))
for e in v.errors():
    print(e.toString())
v.show()
def grab():
    v.grabWindow().save({path!r})
    app.quit()
QTimer.singleShot(1500, grab)
app.exec()
"""
    subprocess.run([sys.executable, "-c", code], timeout=40)


base = out[:-4] if out.endswith(".png") else out
shot("graphit", base + "-graphit.png")
shot("porzellan", base + "-porzellan.png")
