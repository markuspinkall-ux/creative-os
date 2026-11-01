"""Startpunkt: `creative-pictures [Bild]` – ohne Bild öffnet sich die Sammlung."""

import os
import signal
import sys
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

from .backend import Pictures

HERE = Path(__file__).resolve().parent


def main():
    QQuickStyle.setStyle("Basic")
    app = QGuiApplication(sys.argv)
    app.setApplicationName("Creative Pictures")
    app.setOrganizationName("Creative OS")
    app.setDesktopFileName("creative-pictures")
    app.setWindowIcon(QIcon.fromTheme("creative-pictures"))

    engine = QQmlApplicationEngine()
    for d in (HERE.parent.parent / "shell" / "creative_shell" / "qml", Path("/usr/lib/creative-shell/creative_shell/qml")):
        if (d / "Creative" / "qmldir").exists():
            engine.addImportPath(str(d))
            break
    pics = Pictures()
    files = []
    for a in sys.argv[1:]:
        if a.startswith("file://"):
            a = QUrl(a).toLocalFile()
        if not a.startswith("-") and os.path.isfile(a):
            files.append(a)
    if files:
        pics.open_file(files[0])
    engine.rootContext().setContextProperty("pics", pics)
    engine.load(QUrl.fromLocalFile(str(HERE / "qml" / "Main.qml")))
    if not engine.rootObjects():
        return 1
    if "--selftest" in sys.argv:
        print("Creative Pictures: Selbsttest bestanden")
        return 0

    signal.signal(signal.SIGINT, lambda *_: app.quit())
    ticker = QTimer()
    ticker.start(300)
    ticker.timeout.connect(lambda: None)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
